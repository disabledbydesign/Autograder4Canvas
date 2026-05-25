#!/usr/bin/env python3
"""
Launch the Research Comparison tool.

This is a separate entry point from the main GUI — intentionally isolated
so the research panel cannot be shown during a demo or production session.

Usage:
    python3 scripts/launch_research.py            # online mode (uses Canvas creds if present)
    python3 scripts/launch_research.py --offline  # offline mode (browse stored runs only)
"""

import os
import sys
from pathlib import Path

# ── Path setup (mirrors src/gui/app.py) ─────────────────────────────────────
_src_dir = str(Path(__file__).resolve().parent.parent / "src")
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)

_app_venv_sp = Path.home() / ".autograder4canvas" / "venv" / "lib"
if _app_venv_sp.exists():
    for _sp in _app_venv_sp.glob("python*/site-packages"):
        _sp_str = str(_sp)
        if _sp_str not in sys.path:
            sys.path.append(_sp_str)

# ── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication

    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(sys.argv)
    app.setApplicationName("Autograder4Canvas — Research")
    app.setOrganizationName("CanvasAutograder")

    from gui.styles import build_app_qss
    app.setStyleSheet(build_app_qss())

    offline = "--offline" in sys.argv

    api = None
    if not offline:
        # Load credentials (same logic as app.py)
        from credentials import get_active_profile, load_credentials
        data = load_credentials()
        _, profile = get_active_profile(data) if data else (None, {})

        url   = profile.get("canvas_base_url")   or os.environ.get("CANVAS_BASE_URL", "")
        token = profile.get("canvas_api_token")  or os.environ.get("CANVAS_API_TOKEN", "")

        if url and token:
            from automation.canvas_helpers import CanvasAutomationAPI
            api = CanvasAutomationAPI(base_url=url, api_token=token)

    from insights.insights_store import InsightsStore
    store = InsightsStore()

    from research.research_window import ResearchWindow
    window = ResearchWindow(api=api, store=store)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
