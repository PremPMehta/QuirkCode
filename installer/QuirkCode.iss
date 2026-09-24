; Inno Setup script for QuirkCode
; Requires: QuirkCode.exe already built in dist\
; Build: ISCC installer\QuirkCode.iss

#define MyAppName "QuirkCode"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "QuirkCode"
#define MyAppExeName "QuirkCode.exe"

[Setup]
AppId={{A7C3E91B-4F2D-4B8A-9E1C-QuirkCode0001}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=..\dist\installer
OutputBaseFilename=QuirkCodeSetup
SetupIconFile=..\assets\quirkcode.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional icons:"; Flags: unchecked

[Files]
Source: "..\dist\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\config.json"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\HOW_TO_USE.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\assets\quirkcode.ico"; DestDir: "{app}\assets"; Flags: ignoreversion

[Dirs]
Name: "{app}\logs"

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\assets\quirkcode.ico"
Name: "{group}\{#MyAppName} - How to Use"; Filename: "{app}\HOW_TO_USE.txt"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\assets\quirkcode.ico"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName}"; Flags: nowait postinstall skipifsilent
