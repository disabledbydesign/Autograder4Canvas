@echo off
setlocal enabledelayedexpansion

echo ========================================
echo    Autograder4Canvas — Full Build
echo    Step 1: PyInstaller bundle
echo    Step 2: Inno Setup installer .exe
echo ========================================
echo.

:: Always run from this script's directory (build\windows\)
cd /d "%~dp0"

:: -------------------------------------------------------
:: Check for Python
:: -------------------------------------------------------
set "PYTHON_CMD="
where python >nul 2>&1
if %ERRORLEVEL% == 0 (
    for /f "tokens=2 delims= " %%v in ('python --version 2^>^&1') do set "PY_VER=%%v"
    if "!PY_VER:~0,1!"=="3" set "PYTHON_CMD=python"
)
if not defined PYTHON_CMD where python3 >nul 2>&1 && set "PYTHON_CMD=python3"
if not defined PYTHON_CMD (
    for /d %%d in ("%LOCALAPPDATA%\Programs\Python\Python3*") do (
        if exist "%%d\python.exe" set "PYTHON_CMD=%%d\python.exe"
    )
)
if not defined PYTHON_CMD (
    echo ERROR: Python 3 not found.
    echo Install from https://www.python.org/downloads/ then re-run this script.
    pause
    exit /b 1
)
echo [OK] Python: !PYTHON_CMD!

:: -------------------------------------------------------
:: Check for Inno Setup (iscc.exe)
:: -------------------------------------------------------
set "ISCC="
where iscc >nul 2>&1 && set "ISCC=iscc"
if not defined ISCC if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if not defined ISCC if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe"       set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"
if not defined ISCC if exist "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe" set "ISCC=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"
if not defined ISCC (
    echo.
    echo ERROR: Inno Setup 6 not found.
    echo.
    echo Install it from: https://jrsoftware.org/isdl.php
    echo   - Click "Download Inno Setup"
    echo   - Run innosetup-6.x.x.exe ^(needs admin on this build machine, one time only^)
    echo   - Re-run this script
    echo.
    pause
    exit /b 1
)
echo [OK] Inno Setup: !ISCC!
echo.

:: -------------------------------------------------------
:: Step 1: Build PyInstaller bundle
:: -------------------------------------------------------
echo [1/2] Building PyInstaller bundle...
echo       Installing deps + bundling app. First run takes 5-15 min.
echo.
set "NO_PAUSE=1"
call build_exe.bat
set "BUILD_RESULT=%ERRORLEVEL%"
set "NO_PAUSE="
if %BUILD_RESULT% neq 0 (
    echo.
    echo ERROR: PyInstaller build failed. See output above.
    pause
    exit /b 1
)

if not exist "dist\Autograder4Canvas\Autograder4Canvas.exe" (
    echo.
    echo ERROR: Expected output not found: dist\Autograder4Canvas\Autograder4Canvas.exe
    echo Check PyInstaller output above for errors.
    pause
    exit /b 1
)
echo [OK] PyInstaller bundle ready.
echo.

:: -------------------------------------------------------
:: Step 2: Compile Inno Setup installer
:: -------------------------------------------------------
echo [2/2] Compiling installer...
"!ISCC!" Autograder4Canvas.iss
if %ERRORLEVEL% neq 0 (
    echo.
    echo ERROR: Inno Setup compilation failed. See output above.
    pause
    exit /b 1
)

if not exist "dist\Autograder4Canvas-Setup.exe" (
    echo.
    echo ERROR: Expected installer not found: dist\Autograder4Canvas-Setup.exe
    pause
    exit /b 1
)

:: -------------------------------------------------------
:: Done — report output
:: -------------------------------------------------------
echo.
echo ========================================
echo    Done!
echo ========================================
echo.
echo Installer: %~dp0dist\Autograder4Canvas-Setup.exe
echo.
for %%f in ("%~dp0dist\Autograder4Canvas-Setup.exe") do (
    set /a SIZE_MB=%%~zf / 1048576
    echo Size: !SIZE_MB! MB
)
echo.
echo Share dist\Autograder4Canvas-Setup.exe with testers.
echo They double-click it to install. No Python needed, no admin prompt.
echo.
pause
