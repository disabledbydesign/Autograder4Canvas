# Autograder4Canvas - Project Memory

## Architecture (unified bootstrap)
- `run.bat` / `run.sh` — minimal shell wrappers (~15 lines), just find Python and call `src/bootstrap.py`
- `src/bootstrap.py` — all setup logic: Python check, venv, pip install, credential migration, then exec into `src/run_autograder.py`
- `src/run_autograder.py` — main autograder (renamed from `run_autograder_v1-3.py`), no longer handles venv/pip
- Credentials stored in `credentials.json` in platform config dir (`%LOCALAPPDATA%\CanvasAutograder\` etc.)
- Old `credentials.bat` / env var formats auto-migrated on first run

## Key Files
- `build/windows/Autograder4Canvas/` — installer-based Windows build (INSTALL.bat)
- `build/linux/Autograder4Canvas/` — Linux installer (install.sh)
- `build/mac/Autograder4Canvas.app/` — macOS app bundle
- `src/` — canonical source
- `src/autograder_utils.py` — cross-platform config/output utilities

## Known Windows Issues Fixed
- `open()` without encoding='utf-8' crashes on Windows with non-ASCII text
- Microsoft Store Python stubs detected and warned about
- `chcp 65001` in run.bat for UTF-8/emoji output in cmd.exe

## Python Requirements
requests, python-dateutil, pytz, openpyxl, pandas

## Memories
- [project_bootstrap_refactor](project_bootstrap_refactor.md) — bootstrap consolidation context
- [MLX Metal Launch](mlx_metal_launch.md) — terminal required, caffeinate -id, killed-process hangover needs reboot, warmup pattern, checkpoint saves
