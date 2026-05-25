"""
process_keepalive — Cross-platform sleep prevention for long-running jobs.

Long jobs (Insights pipeline, research-panel comparisons) span hundreds of LLM
calls and easily exceed an hour. If the Mac sleeps mid-run we get Metal
deadlocks on MLX, dropped Ollama connections, and incomplete data. This module
gives any caller a single context-manageable handle that:

  - macOS:   spawns `caffeinate -s -w <pid>` (system sleep blocked, auto-cleans
             when our process dies)
  - Windows: disables AC standby timeout via `powercfg`, restoring on exit
  - Linux:   spawns `systemd-inhibit` if available, otherwise no-op

Why factor this out: the InsightsEngine has had this logic inline for months.
The research engine needs the same protection but shouldn't double-spawn
caffeinate if the production pipeline is already running. A shared helper
keeps the behavior consistent and makes idempotency explicit (the keeper
checks if its own subprocess is still alive before spawning a new one).

Usage:
    keeper = SleepPreventer(enabled=True)
    keeper.start()
    try:
        ... long job ...
    finally:
        keeper.stop()

Or as a context manager:
    with SleepPreventer(enabled=True):
        ... long job ...
"""

import logging
import os
import platform
import shutil
import subprocess as _sp
from typing import Optional

log = logging.getLogger(__name__)


class SleepPreventer:
    """Cross-platform keep-awake handle for long-running jobs.

    Idempotent: calling `start()` while already active is a no-op (it checks
    that its tracked subprocess is still alive). Safe to call `stop()`
    repeatedly. Designed so multiple cooperating components can each guard
    their own scope without stepping on each other — the underlying
    `caffeinate -s -w <pid>` process auto-terminates when the parent process
    exits, so leaks are bounded.
    """

    def __init__(self, enabled: bool = True):
        self._enabled = enabled
        self._proc: Optional[_sp.Popen] = None
        self._original_standby: Optional[str] = None  # Windows only

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Begin preventing system sleep.

        macOS:   caffeinate -s -w <pid>
        Windows: powercfg standby-timeout-ac 0 (records prior value)
        Linux:   systemd-inhibit (if available)

        No-op if disabled or if a subprocess is already active.
        """
        if not self._enabled:
            return

        # Already running — don't spawn a second process
        if self._proc is not None:
            if self._proc.poll() is None:
                return  # still alive
            self._proc = None  # died; fall through to restart

        system = platform.system()
        try:
            if system == "Darwin":
                # -s prevents system sleep (stronger than -i which only prevents idle)
                # -w ties to our process ID so it auto-cleans if we crash
                self._proc = _sp.Popen(
                    ["caffeinate", "-s", "-w", str(os.getpid())],
                    stdout=_sp.DEVNULL, stderr=_sp.DEVNULL,
                )
                log.info("Sleep prevention active (caffeinate -s)")

            elif system == "Windows":
                try:
                    result = _sp.run(
                        ["powercfg", "/query", "SCHEME_CURRENT", "SUB_SLEEP",
                         "STANDBYIDLE"],
                        capture_output=True, text=True, timeout=5,
                    )
                    for line in result.stdout.splitlines():
                        if "Current AC Power Setting Index" in line:
                            self._original_standby = line.split("0x")[-1].strip()
                            break
                except Exception:
                    self._original_standby = None

                _sp.run(
                    ["powercfg", "/change", "standby-timeout-ac", "0"],
                    capture_output=True, timeout=5,
                )
                log.info("Sleep prevention active (powercfg standby disabled)")

            elif system == "Linux":
                if shutil.which("systemd-inhibit"):
                    self._proc = _sp.Popen(
                        ["systemd-inhibit", "--what=sleep",
                         "--who=Autograder4Canvas",
                         "--why=Running long analysis",
                         "sleep", "infinity"],
                        stdout=_sp.DEVNULL, stderr=_sp.DEVNULL,
                    )
                    log.info("Sleep prevention active (systemd-inhibit)")

        except Exception as e:
            log.debug("Could not start sleep prevention: %s", e)

    def stop(self) -> None:
        """Restore normal sleep behavior. Safe to call repeatedly."""
        # Kill caffeinate / systemd-inhibit (macOS / Linux)
        if self._proc is not None:
            try:
                self._proc.terminate()
            except Exception:
                pass
            self._proc = None

        # Restore Windows standby timeout
        if platform.system() == "Windows" and self._original_standby:
            try:
                # Hex seconds → minutes (powercfg /change uses minutes)
                minutes = max(1, int(self._original_standby, 16) // 60)
                _sp.run(
                    ["powercfg", "/change", "standby-timeout-ac", str(minutes)],
                    capture_output=True, timeout=5,
                )
            except Exception:
                # Fallback: restore to 30 minutes
                try:
                    _sp.run(
                        ["powercfg", "/change", "standby-timeout-ac", "30"],
                        capture_output=True, timeout=5,
                    )
                except Exception:
                    pass
            self._original_standby = None
            log.info("Sleep prevention stopped (standby restored)")

    # ------------------------------------------------------------------
    # Context manager sugar
    # ------------------------------------------------------------------

    def __enter__(self) -> "SleepPreventer":
        self.start()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.stop()
