# Windows VM Handoff — Autograder4Canvas GUI

**For**: Agent running inside a Windows 10/11 VM  
**Goal**: Build the installer, then verify the app launches correctly.  
**Repo**: Clone from the same repo this file lives in (or it's already cloned).

---

## What this app is

Autograder4Canvas is a PySide6 desktop app (amber terminal aesthetic) that connects to Canvas LMS to help instructors grade and analyze student submissions. It has a first-run setup dialog (Canvas URL + API token), then a main window with nav tabs: Quick Run, Bulk Run, Review, Automation, Settings.

The GUI entry point is `src/gui_main.py`. The legacy TUI entry point is `src/run_autograder.py` — ignore that one.

---

## Step 0 — One-time build machine setup (do this first, once)

Before building, Inno Setup must be installed on this VM. This requires admin, but only needs to happen once.

1. Open a browser and go to: `https://jrsoftware.org/isdl.php`
2. Download `innosetup-6.x.x.exe`
3. Run it — accept defaults, click through the installer
4. Done. `iscc.exe` will now be in `C:\Program Files (x86)\Inno Setup 6\`

Python 3 is also required. If not present:
1. Go to `https://www.python.org/downloads/`
2. Download Python 3.12 — run installer, check "Add Python to PATH"
3. Done.

---

## Step 1 — Build the installer

```
cd build\windows
build_installer.bat
```

This script does everything in sequence:
- Installs PyInstaller + all Python dependencies via pip
- Bundles the app into a self-contained folder using PyInstaller
- Compiles `Autograder4Canvas-Setup.exe` using Inno Setup

**First run takes 10-20 minutes** (pip downloads ~2 GB of packages including PySide6).  
Subsequent runs are much faster (packages already cached).

Output: `build\windows\dist\Autograder4Canvas-Setup.exe`

---

## Step 2 — Test the installer

Run `dist\Autograder4Canvas-Setup.exe`. This is what a real user would receive.

**No admin prompt should appear.** Installs to `%LOCALAPPDATA%\Programs\Autograder4Canvas`.

**SmartScreen warning is expected.** Because the installer isn't code-signed, Windows will show "Windows protected your PC." This is normal for unsigned software. Click **"More info"** → **"Run anyway"** to proceed. Note whether the warning appeared so we know what real users will see.

Verify:
- [ ] Installer wizard opens (no terminal window)
- [ ] Welcome screen describes the app in plain language
- [ ] "Add a shortcut to my Desktop" checkbox is present and checked by default
- [ ] Progress bar runs during install
- [ ] "Launch Autograder4Canvas" checkbox appears on Finish screen
- [ ] Checking it and clicking Finish launches the app (no terminal window, no console)
- [ ] App icon appears in taskbar (amber icon, not a generic Python icon)
- [ ] Desktop shortcut created
- [ ] App appears in Add/Remove Programs (Settings → Apps)

---

## Step 3 — Test the app

- [ ] Setup dialog appears: two-panel layout, Canvas URL + token fields
- [ ] "HIGH SCHOOL DEMO" button works — enters main window without real Canvas credentials
- [ ] Main window loads: Quick Run | Bulk Run | Review | Automation | Settings tabs
- [ ] Switching between tabs doesn't crash
- [ ] No terminal/console window visible at any point

---

## What to report back

```
BUILD
build_installer.bat result: PASS / FAIL
Time taken: X min
Output file size: X MB
Any errors during build:

INSTALLER TEST
Admin prompt appeared: Y / N  (should be N)
SmartScreen warning appeared: Y / N  (expected — click More info → Run anyway)
Wizard opened cleanly: Y / N
Desktop shortcut created: Y / N
App launched from shortcut: Y / N
Console window visible: Y / N  (should be N)
Correct icon in taskbar: Y / N

APP TEST
Setup dialog appeared: Y / N
Demo mode worked: Y / N
Main window loaded: Y / N
Tab switching crashes: Y / N
Notes: [any errors, warnings, unexpected behavior]

System info:
Windows version:
Python version:
Admin rights available on this VM: Y / N
```

---

## Do NOT do

- Do not enter real Canvas credentials — use Demo mode for all testing
- Do not modify `src/` source files — report issues, don't fix them
- Do not commit anything from the VM — report findings only

---

## Fallback tracks (if build_installer.bat fails)

### Track A — Script-based installer (INSTALL.bat)

Older approach. Copies src/ and creates a venv. No standalone exe.

1. Navigate to `build\windows\Autograder4Canvas\`
2. Double-click `INSTALL.bat`
3. Answer prompts, wait for pip install

### Track B — PyInstaller only (no Inno Setup wrapper)

If Inno Setup isn't available, the bare PyInstaller bundle still works.

1. `cd build\windows`
2. `build_exe.bat`
3. Output: `dist\Autograder4Canvas\Autograder4Canvas.exe` — double-click directly

