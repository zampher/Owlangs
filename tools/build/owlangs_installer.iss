; Owlangs Windows Installer Script for Inno Setup
; This script creates a professional Windows installer

#define MyAppName "Owlangs"
#define MyAppVersion "1.1.0.0"
; MyAppEdition: pass via /DMyAppEdition=Basic|Pro|Enterprise when calling ISCC (default Pro)
#ifndef MyAppEdition
#define MyAppEdition "Pro"
#endif
#define MyAppPublisher "Owlangs Team"
#define MyAppURL "https://github.com/your-repo/Owlangs"
; Backend exe: fixed name (no version) for simpler version updates
#define MyAppExeName "Owlangs-win.exe"
#define MyAppFullExeName "Owlangs-win.exe"

[Setup]
; NOTE: The value of AppId uniquely identifies this application.
; Do not use the same AppId value in installers for other applications.
AppId={{A1B2C3D4-E5F6-7890-ABCD-EF1234567890}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={autopf}\Owlangs\Document Agent
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
DisableDirPage=no
DisableProgramGroupPage=no
; Use English license for installer wizard to avoid encoding/garbled text on some systems
LicenseFile=LICENSE_EN.txt
OutputDir=build\installer
; Output: Owlangs-{Edition}-{Version}-x64.exe (e.g. Owlangs-Basic-1.0.0.0-x64.exe)
OutputBaseFilename=Owlangs-{#MyAppEdition}-{#MyAppVersion}-x64
SetupIconFile=Owlangs.ico
Compression=lzma
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "chinesesimp"; MessagesFile: "compiler:Languages\ChineseSimplified.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "quicklaunchicon"; Description: "{cm:CreateQuickLaunchIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked; OnlyBelowVersion: 6.1; Check: not IsAdminInstallMode

[Files]
; Application files
Source: "dist\{#MyAppExeName}"; DestDir: "{app}\bin"; Flags: ignoreversion
Source: "dist\{#MyAppFullExeName}"; DestDir: "{app}\bin"; Flags: ignoreversion; Check: FileExists(ExpandConstant('{app}\bin\{#MyAppFullExeName}'))

; Configuration templates (new config structure)
Source: "configs\system.json.template"; DestDir: "{app}\config"; Flags: ignoreversion
Source: "configs\platforms.json.template"; DestDir: "{app}\config"; Flags: ignoreversion
Source: "configs\secrets.json.template"; DestDir: "{app}\config"; Flags: ignoreversion
Source: "configs\local.json.template"; DestDir: "{app}\config"; Flags: ignoreversion
Source: "configs\local_users.json.template"; DestDir: "{app}\config"; Flags: ignoreversion; Check: FileExists("configs\local_users.json.template")

; Additional config files if they exist
Source: "configs\app_config.json"; DestDir: "{app}\config"; Flags: ignoreversion; Check: FileExists("configs\app_config.json")

; Launcher scripts
Source: "tools\build\windows\Owlangs.bat"; DestDir: "{app}"; Flags: ignoreversion
Source: "tools\build\windows\Owlangs-full.bat"; DestDir: "{app}"; Flags: ignoreversion

; Documentation
Source: "README.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "LICENSE_EN.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "LICENSE_ZH.txt"; DestDir: "{app}"; Flags: ignoreversion

; Optional: Pandoc + pdflatex for PDF workflow DOCX/PDF export (included when built with /DINCLUDE_PANDOC=1)
; Pandoc stays in {app}\3rdParty\windows (read-only is fine for DOCX export).
; pdflatex (TinyTeX/XeLaTeX) goes to {commonappdata} so it can write fmt files
; and font caches at runtime without admin privileges.
#ifdef INCLUDE_PANDOC
Source: "..\..\build\installer_stage\3rdParty\windows\*"; DestDir: "{app}\3rdParty\windows"; Excludes: "pdflatex"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\..\build\installer_stage\3rdParty\windows\pdflatex"; DestDir: "{commonappdata}\Owlangs\3rdParty\windows\pdflatex"; Flags: ignoreversion recursesubdirs createallsubdirs
#endif

[UninstallDelete]
; Remove pdflatex binaries from shared app data on uninstall (configs/logs/models are kept)
Type: filesandordirs; Name: "{commonappdata}\Owlangs\3rdParty\windows\pdflatex"

[Icons]
Name: "{group}\{#MyAppName} Lite"; Filename: "{app}\owlangs.bat"; WorkingDir: "{app}"
Name: "{group}\{#MyAppName} Full"; Filename: "{app}\owlangs-full.bat"; WorkingDir: "{app}"; Check: FileExists(ExpandConstant('{app}\owlangs-full.bat'))
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
; Desktop: Console (control panel) + Chrome/localhost:8800
Name: "{autodesktop}\Owlangs 控制台"; Filename: "{app}\owlangs.bat"; WorkingDir: "{app}"; Tasks: desktopicon
Name: "{autodesktop}\Owlangs 网页 (localhost:8800)"; Filename: "{pf}\Google\Chrome\Application\chrome.exe"; Parameters: "http://localhost:8800"; Tasks: desktopicon; Check: FileExists(ExpandConstant('{pf}\Google\Chrome\Application\chrome.exe'))
Name: "{autodesktop}\Owlangs 网页 (localhost:8800)"; Filename: "{pf32}\Google\Chrome\Application\chrome.exe"; Parameters: "http://localhost:8800"; Tasks: desktopicon; Check: not FileExists(ExpandConstant('{pf}\Google\Chrome\Application\chrome.exe')) and FileExists(ExpandConstant('{pf32}\Google\Chrome\Application\chrome.exe'))
Name: "{autodesktop}\Owlangs 网页 (localhost:8800)"; Filename: "rundll32.exe"; Parameters: "url.dll,FileProtocolHandler http://localhost:8800"; Tasks: desktopicon; Check: not FileExists(ExpandConstant('{pf}\Google\Chrome\Application\chrome.exe')) and not FileExists(ExpandConstant('{pf32}\Google\Chrome\Application\chrome.exe'))
Name: "{userappdata}\Microsoft\Internet Explorer\Quick Launch\Owlangs 控制台"; Filename: "{app}\owlangs.bat"; WorkingDir: "{app}"; Tasks: quicklaunchicon

[Run]
; Grant Users group Modify permission on Owlangs data directory so the backend
; (running as a normal user) can read/write configs, logs, models, etc.
Filename: "{sys}\icacls.exe"; Parameters: "{commonappdata}\Owlangs /grant Users:(OI)(CI)M /T"; StatusMsg: "Setting permissions..."; Flags: runhidden nowait
Filename: "{app}\owlangs.bat"; Description: "{cm:LaunchProgram,{#MyAppName}}"; Flags: nowait postinstall skipifsilent

[Code]
var
  ConfigDirPage: TInputDirWizardPage;

procedure InitializeWizard;
begin
  // Create a custom page for configuration directory selection
  ConfigDirPage := CreateInputDirPage(wpSelectDir,
    'Configuration Directory', 'Where should configuration files be stored?',
    'Please select the directory where Owlangs configuration files will be stored.' + #13#10 + #13#10 +
    'The default location is C:\ProgramData\Owlangs, which allows all users to access the configuration.',
    False, '');
  ConfigDirPage.Add('Configuration directory:');
  ConfigDirPage.Values[0] := ExpandConstant('{commonappdata}\Owlangs');
end;

function ShouldSkipPage(PageID: Integer): Boolean;
begin
  Result := False;
end;

function NextButtonClick(CurPageID: Integer): Boolean;
begin
  Result := True;
  if CurPageID = ConfigDirPage.ID then
  begin
    // Validate the configuration directory
    if not DirExists(ConfigDirPage.Values[0]) then
    begin
      if not CreateDir(ConfigDirPage.Values[0]) then
      begin
        MsgBox('Cannot create the configuration directory. Please select a different location.', mbError, MB_OK);
        Result := False;
      end;
    end;
  end;
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  ConfigDir: String;
  ConfigFiles: TArrayOfString;
  TemplateFiles: TArrayOfString;
  ConfigFileName: String;
  I: Integer;
begin
  if CurStep = ssPostInstall then
  begin
    ConfigDir := ConfigDirPage.Values[0];
    
    // Copy configuration files to the selected directory (new config structure)
    SetArrayLength(ConfigFiles, 4);
    ConfigFiles[0] := 'system.json.template';
    ConfigFiles[1] := 'platforms.json.template';
    ConfigFiles[2] := 'secrets.json.template';
    ConfigFiles[4] := 'local.json.template';
    
    for I := 0 to GetArrayLength(ConfigFiles) - 1 do
    begin
      if FileExists(ExpandConstant('{app}\config\' + ConfigFiles[I])) then
      begin
        // Remove .template suffix for runtime files
        ConfigFileName := ConfigFiles[I];
        StringChangeEx(ConfigFileName, '.template', '', False);
        if not FileExists(ConfigDir + '\' + ConfigFileName) then
        begin
          FileCopy(ExpandConstant('{app}\config\' + ConfigFiles[I]), ConfigDir + '\' + ConfigFileName, False);
        end;
      end;
    end;
    
    // Create secrets.json from template if it doesn't exist
    if not FileExists(ConfigDir + '\secrets.json') then
    begin
      if FileExists(ConfigDir + '\secrets.json.template') then
      begin
        FileCopy(ConfigDir + '\secrets.json.template', ConfigDir + '\secrets.json', False);
      end;
    end;
    
    // Create local.json from template if it doesn't exist
    if not FileExists(ConfigDir + '\local.json') then
    begin
      if FileExists(ConfigDir + '\local.json.template') then
      begin
        FileCopy(ConfigDir + '\local.json.template', ConfigDir + '\local.json', False);
      end;
    end;
    
    // Create app_config.json from template if it doesn't exist
    if not FileExists(ConfigDir + '\app_config.json') then
    begin
      if FileExists(ConfigDir + '\app_config.json.template') then
      begin
        FileCopy(ConfigDir + '\app_config.json.template', ConfigDir + '\app_config.json', False);
      end
      else if FileExists(ExpandConstant('{app}\config\app_config.json')) then
      begin
        FileCopy(ExpandConstant('{app}\config\app_config.json'), ConfigDir + '\app_config.json', False);
      end;
    end;

    // Force-copy template files to config directory (overwrite existing).
    // This ensures schema upgrades from templates are applied on reinstall/upgrade.
    // secrets.json.template is excluded: API keys are managed by the backend merge logic.
    SetArrayLength(TemplateFiles, 4);
    TemplateFiles[0] := 'system.json.template';
    TemplateFiles[1] := 'platforms.json.template';
    TemplateFiles[2] := 'local.json.template';
    TemplateFiles[3] := 'local_users.json.template';

    for I := 0 to GetArrayLength(TemplateFiles) - 1 do
    begin
      if FileExists(ExpandConstant('{app}\config\' + TemplateFiles[I])) then
      begin
        FileCopy(ExpandConstant('{app}\config\' + TemplateFiles[I]), ConfigDir + '\' + TemplateFiles[I], False);
      end;
    end;

    // Also copy app_config.json as template if it exists (for schema upgrades)
    if FileExists(ExpandConstant('{app}\config\app_config.json')) then
    begin
      FileCopy(ExpandConstant('{app}\config\app_config.json'), ConfigDir + '\app_config.json.template', False);
    end;
  end;
end;

function InitializeUninstallProgressForm(): Boolean;
begin
  Result := True;
end;

function IsRedisRunning(): Boolean;
var
  ResultCode: Integer;
begin
  // Check if redis-server.exe is running
  Result := False;
  if Exec('tasklist', '/FI "IMAGENAME eq redis-server.exe" /NH', '', SW_HIDE, ewWaitUntilTerminated, ResultCode) then
  begin
    if ResultCode = 0 then
    begin
      Result := True;
    end;
  end;
end;

procedure StopRedis();
var
  ResultCode: Integer;
  RedisCliPath: String;
  AppDir: String;
begin
  AppDir := ExpandConstant('{app}');
  
  // Try to find redis-cli.exe in common locations (match actual package layout)
  RedisCliPath := AppDir + '\3rdParty\windows\Redis-x64-3.0.504\redis-cli.exe';
  if not FileExists(RedisCliPath) then
  begin
    // Fallback for older or alternate layouts
    RedisCliPath := AppDir + '\3rdParty\windows\redis\redis-cli.exe';
  end;
  
  // First try graceful shutdown via redis-cli
  if FileExists(RedisCliPath) then
  begin
    Log('Stopping Redis gracefully using: ' + RedisCliPath);
    Exec(RedisCliPath, '-h 127.0.0.1 -p 6379 shutdown', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
    Sleep(3000); // Wait for Redis to stop
  end;
  
  // If still running, force kill the process
  if IsRedisRunning() then
  begin
    Log('Redis still running, forcing termination...');
    Exec('taskkill', '/F /IM redis-server.exe /T', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
    Sleep(2000);
  end;
end;

procedure StopOwlangsProcesses();
var
  ResultCode: Integer;
begin
  // Stop OwlangsLauncher (desktop launcher)
  Log('Stopping OwlangsLauncher...');
  Exec('taskkill', '/F /IM OwlangsLauncher.exe /T', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  Sleep(1000);

  // Stop Flutter Windows frontend (owlangs.exe)
  Log('Stopping owlangs frontend...');
  Exec('taskkill', '/F /IM owlangs.exe /T', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  Sleep(1000);

  // Stop backend executable (Owlangs-win.exe)
  Log('Stopping Owlangs backend...');
  Exec('taskkill', '/F /IM Owlangs-win.exe /T', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  Sleep(1000);
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  ConfigDir: String;
  Response: Integer;
begin
  if CurUninstallStep = usUninstall then
  begin
    // Check and stop Redis before uninstalling
    if IsRedisRunning() then
    begin
      Log('Redis is running, stopping it before uninstall...');
      StopRedis();
    end;

    // Stop Owlangs application processes (launcher, frontend, backend)
    Log('Stopping Owlangs processes before uninstall...');
    StopOwlangsProcesses();
  end
  else if CurUninstallStep = usPostUninstall then
  begin
    ConfigDir := ExpandConstant('{commonappdata}\Owlangs');
    if DirExists(ConfigDir) then
    begin
      Response := MsgBox('Do you want to remove the configuration files?' + #13#10 + #13#10 +
        'Configuration directory: ' + ConfigDir + #13#10 +
        'This will delete all your settings and API keys.', mbConfirmation, MB_YESNO);
      if Response = IDYES then
      begin
        DelTree(ConfigDir, True, True, True);
      end;
    end;
  end;
end;

