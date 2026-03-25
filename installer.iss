; Project N.O.M.A.D. Inno Setup Script
; AppVersion: 3.1.0

#define MyAppName "Project N.O.M.A.D."
#define MyAppVersion "3.1.0"
#define MyAppPublisher "SysAdminDoc"
#define MyAppURL "https://github.com/SysAdminDoc/nomad-windows"
#define MyAppSupportURL "https://github.com/SysAdminDoc/nomad-windows/issues"
#define MyAppExeName "ProjectNOMAD.exe"
#define MyAppDescription "Project N.O.M.A.D. -- Your offline-first knowledge and AI command center. No Docker required."

[Setup]
AppId={{A1B2C3D4-E5F6-7890-ABCD-EF1234567890}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppSupportURL}
AppUpdatesURL={#MyAppURL}
AppComments={#MyAppDescription}
DefaultDirName={autopf}\ProjectNOMAD
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=.
OutputBaseFilename=ProjectNOMAD-Setup
SetupIconFile=icon.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
UninstallDisplayName={#MyAppName}
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Files]
Source: "dist\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion
Source: "icon.ico"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\icon.ico"; Comment: "{#MyAppDescription}"
Name: "{autostartmenu}\Programs\{#MyAppName}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\icon.ico"; Comment: "{#MyAppDescription}"

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName}"; Flags: nowait postinstall skipifsilent shellexec; Check: not IsAdminInstallMode

[UninstallDelete]
Type: filesandordirs; Name: "{userappdata}\ProjectNOMAD"
