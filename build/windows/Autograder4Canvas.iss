; Autograder4Canvas — Inno Setup 6 installer script
;
; Prerequisites:
;   1. Run build_exe.bat first — PyInstaller output must exist at dist\Autograder4Canvas\
;   2. Install Inno Setup 6 from https://jrsoftware.org/isdl.php
;
; Build the installer:
;   iscc Autograder4Canvas.iss          (from build\windows\)
;   — or open this file in the Inno Setup IDE and press F9
;
; Output: build\windows\dist\Autograder4Canvas-Setup.exe

#define AppName      "Autograder4Canvas"
#define AppVersion   "1.0.0"
#define AppPublisher "Dr. L. June Bloch"
#define AppExeName   "Autograder4Canvas.exe"

[Setup]
; AppId must stay stable across releases — changing it breaks upgrade detection
AppId={{7D44EC67-D0A1-4E69-8BC8-FAF12700160F}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={localappdata}\Programs\{#AppName}
DefaultGroupName={#AppName}

; No UAC prompt — installs to the user's own profile, no admin rights needed
PrivilegesRequired=lowest

; Skip the Start Menu folder page and directory picker — reduces friction for teachers
DisableProgramGroupPage=yes
DisableDirPage=yes

; Installer appearance
WizardStyle=modern
WizardResizable=no
SetupIconFile=Autograder4Canvas\icon.ico
UninstallDisplayIcon={app}\{#AppExeName}

; Output
OutputDir=dist
OutputBaseFilename={#AppName}-Setup
Compression=lzma2/ultra64
SolidCompression=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Messages]
; Override the welcome page body — plain-language description for teachers
WelcomeLabel2=This will install [name/ver] on your computer.%n%nAutograder4Canvas helps you analyze student submissions, run engagement analysis, and manage grading — all on your own computer, with no data sent to the cloud.%n%nClick Next to continue.

[Tasks]
; Desktop shortcut is checked by default — most users expect it
Name: "desktopicon"; Description: "Add a shortcut to my &Desktop"; GroupDescription: "Additional shortcuts:"; Flags: checked

[Files]
; Copy the entire PyInstaller bundle — exe + Qt plugins + all dependencies
Source: "dist\{#AppName}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
; Start Menu shortcut
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExeName}"
; Desktop shortcut (only if user checked the task above)
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Run]
; "Launch now" checkbox on the Finish page
Filename: "{app}\{#AppExeName}"; Description: "&Launch {#AppName}"; Flags: nowait postinstall skipifsilent
