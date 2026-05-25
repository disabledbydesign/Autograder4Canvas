@echo off
setlocal enabledelayedexpansion

echo ========================================
echo    Autograder4Canvas Installer
echo ========================================
echo.

:: -------------------------------------------------------
:: Resolve source directory
:: If run from inside the git repo (build\windows\Autograder4Canvas\),
:: the real src\ lives two levels up. If run from a distributed zip,
:: src\ is right next to this file.
:: -------------------------------------------------------
set "SCRIPT_DIR=%~dp0"
if exist "%SCRIPT_DIR%..\..\src\gui_main.py" (
    set "SRC_DIR=%SCRIPT_DIR%..\..\src"
    set "ICON_SRC=%SCRIPT_DIR%..\Autograder4Canvas\icon.ico"
) else (
    set "SRC_DIR=%SCRIPT_DIR%src"
    set "ICON_SRC=%SCRIPT_DIR%icon.ico"
)

:: -------------------------------------------------------
:: Check for Python 3
:: -------------------------------------------------------
set "PYTHON_CMD="
where python >nul 2>&1
if %ERRORLEVEL% == 0 (
    for /f "tokens=2 delims= " %%v in ('python --version 2^>^&1') do set "PY_VER=%%v"
    if "!PY_VER:~0,1!"=="3" set "PYTHON_CMD=python"
)
if not defined PYTHON_CMD (
    where python3 >nul 2>&1
    if %ERRORLEVEL% == 0 (
        set "PYTHON_CMD=python3"
        for /f "tokens=2 delims= " %%v in ('python3 --version 2^>^&1') do set "PY_VER=%%v"
    )
)

if not defined PYTHON_CMD (
    echo.
    echo  ================================================
    echo   Python is needed but isn't installed yet
    echo  ================================================
    echo.
    echo  Autograder4Canvas runs on Python - a free tool
    echo  used by millions of people. We can download and
    echo  install it for you automatically right now!
    echo.
    set /p AUTO_INSTALL="  Install Python automatically? (Y/N): "
    echo.
    if /i "!AUTO_INSTALL!"=="Y" (
        echo  Step 1 of 2: Downloading Python 3.12...
        echo  ^(This usually takes 1-2 minutes^)
        echo.

        set "PY_PS1=%TEMP%\install_python.ps1"
        >  "!PY_PS1!" echo $arch = if ([Environment]::Is64BitOperatingSystem) { 'amd64' } else { '' }
        >> "!PY_PS1!" echo $ver  = '3.12.8'
        >> "!PY_PS1!" echo $file = "python-$ver" + $(if ($arch) { "-$arch" } else { "" }) + ".exe"
        >> "!PY_PS1!" echo $url  = "https://www.python.org/ftp/python/$ver/$file"
        >> "!PY_PS1!" echo $out  = Join-Path $env:TEMP 'python_installer.exe'
        >> "!PY_PS1!" echo try {
        >> "!PY_PS1!" echo     Invoke-WebRequest -Uri $url -OutFile $out -UseBasicParsing
        >> "!PY_PS1!" echo     Write-Host "  Step 2 of 2: Installing Python (please wait)..."
        >> "!PY_PS1!" echo     $p = Start-Process $out -ArgumentList '/quiet InstallAllUsers=0 PrependPath=1 Include_test=0 SimpleInstall=1' -Wait -PassThru
        >> "!PY_PS1!" echo     Remove-Item $out -Force -ErrorAction SilentlyContinue
        >> "!PY_PS1!" echo     if ($p.ExitCode -ne 0) { Write-Host "  Installer exited with code $($p.ExitCode)"; exit 1 }
        >> "!PY_PS1!" echo     Write-Host "  Python installed!"
        >> "!PY_PS1!" echo     exit 0
        >> "!PY_PS1!" echo } catch {
        >> "!PY_PS1!" echo     Write-Host "  Download failed: $_"
        >> "!PY_PS1!" echo     exit 1
        >> "!PY_PS1!" echo }

        powershell -ExecutionPolicy Bypass -File "!PY_PS1!"
        set "PY_RESULT=!ERRORLEVEL!"
        del "!PY_PS1!" >nul 2>&1

        if !PY_RESULT! == 0 (
            echo.
            echo  Done! Adding Python to this session...
            for /d %%d in ("%LOCALAPPDATA%\Programs\Python\Python3*") do (
                set "PATH=%%d;%%d\Scripts;!PATH!"
            )
            where python >nul 2>&1
            if !ERRORLEVEL! == 0 (
                for /f "tokens=2 delims= " %%v in ('python --version 2^>^&1') do set "PY_VER=%%v"
                set "PYTHON_CMD=python"
            )
        ) else (
            echo.
            echo  Automatic installation did not complete.
            echo  See the manual steps below.
        )
    )
)

if not defined PYTHON_CMD (
    echo.
    echo  ================================================
    echo   Manual Python installation - follow these steps
    echo  ================================================
    echo.
    echo   1. Open your web browser and go to:
    echo        https://www.python.org/downloads/
    echo.
    echo   2. Click the big yellow "Download Python" button
    echo.
    echo   3. Run the file that downloads
    echo.
    echo   4. IMPORTANT - on the first installer screen:
    echo        Check the box "Add Python to PATH"
    echo        ^(it's at the bottom of the window^)
    echo.
    echo   5. Click "Install Now" and wait for it to finish
    echo.
    echo   6. Come back and run INSTALL.bat again
    echo.
    set /p OPEN_BROWSER="  Open python.org in your browser now? (Y/N): "
    if /i "!OPEN_BROWSER!"=="Y" start https://www.python.org/downloads/
    echo.
    goto :END
)

echo  Python ready: !PYTHON_CMD! ^(!PY_VER!^)
echo.

:: -------------------------------------------------------
:: Confirm install location
:: -------------------------------------------------------
set "INSTALL_DIR=%LOCALAPPDATA%\Autograder4Canvas"
set "VENV_DIR=%INSTALL_DIR%\.venv"
set "VENV_PY=%VENV_DIR%\Scripts\python.exe"
set "VENV_PYW=%VENV_DIR%\Scripts\pythonw.exe"

echo This will install Autograder4Canvas to:
echo   %INSTALL_DIR%
echo.
set /p CONFIRM="Continue? (Y/N): "
if /i not "%CONFIRM%"=="Y" (
    echo Installation cancelled.
    goto :END
)

echo.
echo Installing...

:: -------------------------------------------------------
:: Create directory structure
:: -------------------------------------------------------
if not exist "%INSTALL_DIR%" mkdir "%INSTALL_DIR%"

:: Write xcopy exclusion list
set "XCOPY_EXCL=%INSTALL_DIR%\excl.tmp"
>  "%XCOPY_EXCL%" echo __pycache__
>> "%XCOPY_EXCL%" echo .pyc
>> "%XCOPY_EXCL%" echo Trashed
>> "%XCOPY_EXCL%" echo research
>> "%XCOPY_EXCL%" echo Programs
>> "%XCOPY_EXCL%" echo .ruff_cache
>> "%XCOPY_EXCL%" echo .DS_Store

:: Copy src/ (full GUI source tree, excluding dev/legacy directories)
echo   Copying program files...
xcopy /E /I /Y /EXCLUDE:"%XCOPY_EXCL%" "%SRC_DIR%" "%INSTALL_DIR%\src" >nul
del "%XCOPY_EXCL%" >nul 2>&1

:: Copy icon and uninstaller
if exist "%ICON_SRC%" copy "%ICON_SRC%" "%INSTALL_DIR%\icon.ico" >nul
copy "%SCRIPT_DIR%UNINSTALL.bat" "%INSTALL_DIR%\UNINSTALL.bat" >nul 2>&1
if not exist "%INSTALL_DIR%\UNINSTALL.bat" (
    if exist "%SCRIPT_DIR%..\Autograder4Canvas\UNINSTALL.bat" (
        copy "%SCRIPT_DIR%..\Autograder4Canvas\UNINSTALL.bat" "%INSTALL_DIR%\UNINSTALL.bat" >nul
    )
)

:: -------------------------------------------------------
:: Create virtual environment
:: -------------------------------------------------------
echo   Creating virtual environment...
%PYTHON_CMD% -m venv "%VENV_DIR%"
if %ERRORLEVEL% neq 0 (
    echo.
    echo   ERROR: Could not create virtual environment.
    if "!PYTHON_CMD!"=="python" (
        echo   If you installed Python from the Microsoft Store, it may not
        echo   support venv. Install from https://www.python.org/downloads/ instead.
    )
    pause
    exit /b 1
)
echo   Virtual environment created.

:: -------------------------------------------------------
:: Install dependencies
:: Note: includes PySide6 (GUI), sentence-transformers (ML),
::       and faster-whisper (audio). First install takes 5-15 min
::       depending on internet speed (~2-4 GB download).
:: -------------------------------------------------------
echo   Installing required packages...
echo   ^(This may take 5-15 minutes on first install^)
echo.
"%VENV_PY%" -m pip install --quiet --upgrade pip
"%VENV_PY%" -m pip install --quiet -r "%INSTALL_DIR%\src\requirements.txt"
if %ERRORLEVEL% neq 0 (
    echo.
    echo   WARNING: Some packages may not have installed correctly.
    echo   The program may still work for core features.
    echo   Check your internet connection and try re-running INSTALL.bat if needed.
    echo.
)
echo   Packages installed.

:: Download spaCy language model (non-blocking - grading works without it)
echo   Downloading language model for Academic Integrity analysis...
"%VENV_PY%" -m spacy download en_core_web_sm --quiet >nul 2>&1
if %ERRORLEVEL% == 0 (
    echo   Language model ready.
) else (
    echo   Note: Language model unavailable ^(non-critical^).
)

:: -------------------------------------------------------
:: Create launcher batch (for repair/troubleshooting use)
:: The desktop shortcut bypasses this and calls pythonw.exe directly.
:: -------------------------------------------------------
echo   Creating launcher...
(
echo @echo off
echo setlocal
echo set "INSTALL_DIR=%INSTALL_DIR%"
echo set "VENV_PYW=%VENV_PYW%"
echo if not exist "%%VENV_PYW%%" ^(
echo     echo Virtual environment not found. Please re-run INSTALL.bat to repair.
echo     pause
echo     exit /b 1
echo ^)
echo start "" "%%VENV_PYW%%" "%%INSTALL_DIR%%\src\gui_main.py"
) > "%INSTALL_DIR%\Autograder4Canvas.bat"

:: -------------------------------------------------------
:: Create shortcuts via PowerShell
:: Shortcut targets pythonw.exe directly (no console window).
:: -------------------------------------------------------
echo   Creating shortcuts...
set "PS_TMP=%INSTALL_DIR%\shortcuts.ps1"

>  "%PS_TMP%" echo $installDir  = '%INSTALL_DIR%'
>> "%PS_TMP%" echo $pythonwPath = Join-Path $installDir '.venv\Scripts\pythonw.exe'
>> "%PS_TMP%" echo $guiScript   = Join-Path $installDir 'src\gui_main.py'
>> "%PS_TMP%" echo $icoPath     = Join-Path $installDir 'icon.ico'
>> "%PS_TMP%" echo $srcDir      = Join-Path $installDir 'src'
>> "%PS_TMP%" echo $uninstPath  = Join-Path $installDir 'UNINSTALL.bat'
>> "%PS_TMP%" echo $ws          = New-Object -ComObject WScript.Shell
>> "%PS_TMP%" echo(
>> "%PS_TMP%" echo # Resolve real Desktop and Start Menu paths (handles OneDrive redirection)
>> "%PS_TMP%" echo $desktop = [Environment]::GetFolderPath('Desktop')
>> "%PS_TMP%" echo $menuDir = [Environment]::GetFolderPath('Programs')
>> "%PS_TMP%" echo if (-not (Test-Path $menuDir)) { New-Item -Force -ItemType Directory $menuDir ^| Out-Null }
>> "%PS_TMP%" echo(
>> "%PS_TMP%" echo # Desktop shortcut - launches GUI directly, no console window
>> "%PS_TMP%" echo $s = $ws.CreateShortcut((Join-Path $desktop 'Autograder4Canvas.lnk'))
>> "%PS_TMP%" echo $s.TargetPath       = $pythonwPath
>> "%PS_TMP%" echo $s.Arguments        = "`"$guiScript`""
>> "%PS_TMP%" echo $s.WorkingDirectory = $srcDir
>> "%PS_TMP%" echo if (Test-Path $icoPath) { $s.IconLocation = $icoPath }
>> "%PS_TMP%" echo $s.Save()
>> "%PS_TMP%" echo(
>> "%PS_TMP%" echo # Start Menu shortcut
>> "%PS_TMP%" echo $s = $ws.CreateShortcut((Join-Path $menuDir 'Autograder4Canvas.lnk'))
>> "%PS_TMP%" echo $s.TargetPath       = $pythonwPath
>> "%PS_TMP%" echo $s.Arguments        = "`"$guiScript`""
>> "%PS_TMP%" echo $s.WorkingDirectory = $srcDir
>> "%PS_TMP%" echo if (Test-Path $icoPath) { $s.IconLocation = $icoPath }
>> "%PS_TMP%" echo $s.Save()
>> "%PS_TMP%" echo(
>> "%PS_TMP%" echo # Uninstall shortcut in Start Menu
>> "%PS_TMP%" echo $s = $ws.CreateShortcut((Join-Path $menuDir 'Uninstall Autograder4Canvas.lnk'))
>> "%PS_TMP%" echo $s.TargetPath       = $uninstPath
>> "%PS_TMP%" echo $s.WorkingDirectory = $installDir
>> "%PS_TMP%" echo $s.Description      = 'Uninstall Autograder4Canvas'
>> "%PS_TMP%" echo $s.Save()

powershell -ExecutionPolicy Bypass -File "%PS_TMP%"
if %ERRORLEVEL% neq 0 (
    echo.
    echo   Warning: Shortcuts could not be created automatically.
    echo   You can still launch the program by running:
    echo     %INSTALL_DIR%\Autograder4Canvas.bat
)
del "%PS_TMP%" >nul 2>&1

echo.
echo ========================================
echo    Installation Complete!
echo ========================================
echo.
echo Program installed to: %INSTALL_DIR%
echo.
echo You can now run Autograder4Canvas by:
echo   1. Clicking the Desktop shortcut  ^(no terminal window^)
echo   2. Finding it in the Start Menu
echo.
echo To uninstall: run UNINSTALL.bat from %INSTALL_DIR%
echo.

:END
pause
