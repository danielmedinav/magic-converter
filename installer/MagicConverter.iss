; Inno Setup 6.3+ script for Magic Converter.
; Build the PyInstaller folder first (dist\MagicConverter), then:
;   ISCC.exe /DMyAppVersion=1.0.0 installer\MagicConverter.iss

#define MyAppName "Magic Converter"
#ifndef MyAppVersion
  #define MyAppVersion "1.0.0"
#endif
#define MyAppPublisher "Magic Converter"
#define MyAppExeName "MagicConverter.exe"

[Setup]
; Keep this AppId forever: it is how upgrades and the uninstaller find the app.
AppId={{8F3C2A71-5B4E-4D2A-9C1E-7A6B5D4C3E21}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
; Per-user install by default (no admin prompt); the user may choose all users.
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
OutputDir=..\dist\installer
OutputBaseFilename=MagicConverter-Setup-{#MyAppVersion}
SetupIconFile=..\resources\icon.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
UninstallDisplayName={#MyAppName}
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
CloseApplications=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "..\dist\MagicConverter\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent
; In-app updates run the installer with /SILENT /relaunch=1 -> reopen the app afterwards.
Filename: "{app}\{#MyAppExeName}"; Flags: nowait runasoriginaluser; Check: RelaunchAfterUpdate

[UninstallDelete]
; Remove the icon cache; user settings in %APPDATA%\MagicConverter are kept.
Type: filesandordirs; Name: "{userappdata}\MagicConverter\cache"

[Code]
function RelaunchAfterUpdate: Boolean;
begin
  Result := WizardSilent and (ExpandConstant('{param:relaunch|0}') = '1');
end;
