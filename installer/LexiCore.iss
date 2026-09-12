; LexiCore Desktop Commercial Installer
; Packaging-only. LexiCore runtime/core semantics are unchanged.

#define MyAppName "LexiCore"
#define MyAppVersion "1.4.13"
#define MyAppPublisher "LexiCore"
#define MyAppExeName "LexiCore.exe"

[Setup]
AppId={{1E482BE6-9C16-4C7E-AB06-1D8DA42B41EF}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\LexiCore
DefaultGroupName=LexiCore
DisableProgramGroupPage=yes
PrivilegesRequired=admin
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\dist\installer
OutputBaseFilename=LexiCore-Desktop-Setup-v1.4.13
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\{#MyAppExeName}
SetupLogging=yes
CloseApplications=yes
RestartApplications=no
ChangesAssociations=no

[Files]
Source: "..\dist\LexiCore\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\LexiCore"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"
Name: "{autodesktop}\LexiCore"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Buat shortcut LexiCore di Desktop"; GroupDescription: "Shortcut tambahan:"; Flags: unchecked

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Jalankan LexiCore"; Flags: nowait postinstall skipifsilent
