; Morrow for Windows - per-user installer (no admin rights). build.py compiles it with:
;   iscc /DAppVersion=1.0.0 /DSourceDir=<dist\Morrow> /DOutputDir=<dist> /DIconFile=<build\morrow.ico> morrow.iss
; Installs to %LOCALAPPDATA%\Programs\Morrow, adds Morrow to the Start menu (and optionally the desktop) and lists it
; in Settings > Apps. The window keeps its data (what you saved in it) in %LOCALAPPDATA%\Morrow, which
; uninstalling leaves in place so a reinstall finds it again.

#ifndef AppVersion
  #define AppVersion "1.0.0"
#endif
#ifndef SourceDir
  #define SourceDir "dist\Morrow"
#endif
#ifndef OutputDir
  #define OutputDir "dist"
#endif
#ifndef IconFile
  #define IconFile "build\morrow.ico"
#endif

[Setup]
AppId={{E81247BA-698B-569E-A6DE-E1E1C366EEFB}
AppName=Morrow
AppVersion={#AppVersion}
AppVerName=Morrow {#AppVersion}
AppPublisher=Juwen Lie
AppPublisherURL=https://juw12.github.io/morrow/
AppSupportURL=https://github.com/juw12/morrow
DefaultDirName={autopf}\Morrow
DisableDirPage=yes
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir={#OutputDir}
OutputBaseFilename=Morrow-Windows-Setup
SetupIconFile={#IconFile}
UninstallDisplayIcon={app}\Morrow.exe
UninstallDisplayName=Morrow
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
CloseApplications=no
SetupLogging=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{userprograms}\Morrow"; Filename: "{app}\Morrow.exe"; Comment: "Your morning news, curated: merged stories"
Name: "{userdesktop}\Morrow"; Filename: "{app}\Morrow.exe"; Comment: "Your morning news, curated: merged stories"; Tasks: desktopicon

[Run]
Filename: "{app}\Morrow.exe"; Description: "{cm:LaunchProgram,Morrow}"; Flags: nowait postinstall skipifsilent

[UninstallRun]
Filename: "{app}\Morrow.exe"; Parameters: "--stop"; Flags: runhidden waituntilterminated; RunOnceId: "StopMorrow"

[Code]
function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  ResultCode: Integer;
begin
  Result := '';
  { Updating: close an open Morrow window first so its files can be replaced. }
  if FileExists(ExpandConstant('{app}\Morrow.exe')) then
    Exec(ExpandConstant('{app}\Morrow.exe'), '--stop', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
end;
