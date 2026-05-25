@echo off
setlocal
echo ========================================
echo    Building Autograder4Canvas GUI .exe
echo ========================================
echo.
echo This builds the PySide6 GUI as a standalone Windows executable.
echo The resulting exe does NOT require Python on the target machine.
echo Note: faster-whisper and sentence-transformers are excluded to
echo       keep the bundle size manageable (see Autograder4Canvas.spec).
echo.

:: Find Python
set "PYTHON_CMD="
where python >nul 2>&1 && set "PYTHON_CMD=python"
if not defined PYTHON_CMD where python3 >nul 2>&1 && set "PYTHON_CMD=python3"
if not defined PYTHON_CMD (
    for /d %%d in ("%LOCALAPPDATA%\Programs\Python\Python3*") do (
        if exist "%%d\python.exe" set "PYTHON_CMD=%%d\python.exe"
    )
)
if not defined PYTHON_CMD (
    echo ERROR: Python not found. Install from https://www.python.org/downloads/
    pause
    exit /b 1
)

echo Using: %PYTHON_CMD%
echo.

:: Install build dependencies (PySide6 needed for hooks; pyinstaller for build)
echo Installing build dependencies...
%PYTHON_CMD% -m pip install --quiet --upgrade pip
%PYTHON_CMD% -m pip install --quiet pyinstaller pyinstaller-hooks-contrib
%PYTHON_CMD% -m pip install --quiet PySide6
%PYTHON_CMD% -m pip install --quiet ^
    requests python-dateutil pytz openpyxl pandas pyyaml ^
    python-docx pdfminer.six striprtf odfpy ^
    langdetect vaderSentiment textstat ^
    pydantic scikit-learn spacy
echo.

:: Change to this script's directory (spec file is here)
cd /d "%~dp0"

:: Run PyInstaller
echo Running PyInstaller...
echo ^(This takes several minutes — Qt plugins alone are ~150MB^)
echo.
%PYTHON_CMD% -m PyInstaller Autograder4Canvas.spec --noconfirm

if %ERRORLEVEL% == 0 (
    echo.
    echo ========================================
    echo    Build complete!
    echo ========================================
    echo.
    echo Output: %~dp0dist\Autograder4Canvas\
    echo.
    echo Test by running:
    echo   dist\Autograder4Canvas\Autograder4Canvas.exe
    echo.
    echo If the GUI opens cleanly, zip dist\Autograder4Canvas\ for distribution.
    echo Users run Autograder4Canvas.exe directly - no Python install needed.
) else (
    echo.
    echo Build FAILED. Common causes:
    echo   - Missing import in hiddenimports ^(add to .spec and retry^)
    echo   - PySide6 plugin not found ^(ensure PySide6 is pip-installed^)
    echo   - Antivirus blocking PyInstaller bootloader
    echo.
    echo See full error above.
)

echo.
pause
