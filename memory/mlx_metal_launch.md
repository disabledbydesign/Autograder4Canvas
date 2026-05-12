---
name: mlx-metal-launch
description: MLX model launch requirements — caffeinate flags, terminal context, killed-process hangover, checkpoint saves
metadata:
  type: feedback
---

MLX runs MUST be launched from a real terminal, not Claude Code's Bash tool.

**Why:** Claude Code Bash subprocesses that are backgrounded (`&`) become orphaned processes without a valid macOS window server session. Metal GPU access requires that session context. Orphaned background processes hang indefinitely at `mlx_lm.load()` — 0% CPU, model weights never reach memory. Terminal-launched processes (even backgrounded with `&`) inherit the terminal's session and work fine.

**How to apply:** Always launch MLX runs as: `caffeinate -id python3 scripts/...` from a real terminal. Suggest `! <command>` in Claude Code prompt if needed, but that runs foreground and ties up the session — better to open Terminal.app.

**caffeinate flags:** Use `-id` not `-i`. `-i` prevents idle sleep only. `-d` also prevents display sleep. Display sleep stalls Metal kernel compilation and causes deadlocks on long unattended runs. Every MLX launch command in session_log.md has been updated to use `-id`.

**Killed-process hangover:** Killing MLX processes with SIGKILL (hard kill) leaves Metal GPU driver buffers unreleased at the kernel level. After multiple hard kills in one session, new MLX processes hang at model load indefinitely. The only fix is a machine reboot — no Python-level workaround exists. Avoid killing MLX processes mid-run; use KeyboardInterrupt (Ctrl-C) when possible so the finally block runs `unload_mlx_model()`.

**Warmup pattern (run_wellbeing_concern_full_corpus_test.py and others):** Fire a short 8-token inference before the main run to initialize Metal. Do NOT call `unload_mlx_model()` after warmup — leave model cached. Unloading after warmup forces an immediate reload which can hang on Metal memory reclaim.

**Checkpoint saves:** Long runs (4-5h, 46 students × 5 passes) should checkpoint after each complete pass. The `save_results()` function takes an optional `path` parameter; pre-compute the path before the loop and pass it to each checkpoint call.
