; NOMAD Field Desk Inno Setup Script
; AppVersion: 7.1.0

#define MyAppName "NOMAD Field Desk"
#define MyAppVersion "7.1.0"
#define MyAppPublisher "SysAdminDoc"
#define MyAppURL "https://github.com/SysAdminDoc/project-nomad-desktop"
#define MyAppSupportURL "https://github.com/SysAdminDoc/project-nomad-desktop/issues"
#define MyAppExeName "NOMADFieldDesk.exe"
#define MyAppDescription "Desktop-first offline preparedness and field operations workspace."

[Setup]
AppId={{A7ABF8AE-546E-49E7-BF64-6AF70FA552D3}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppSupportURL}
AppUpdatesURL={#MyAppURL}
AppComments={#MyAppDescription}
DefaultDirName={autopf}\NOMAD Field Desk
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=.
OutputBaseFilename=NOMAD-Setup
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
Type: filesandordirs; Name: "{userappdata}\NOMADFieldDesk"
