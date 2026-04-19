; NSIS Installer Script for Owlangs Desktop Version
; This script creates a Windows installer that packages:
; - Backend EXE (Owlangs-*.exe)
; - Flutter Windows EXE (desktop frontend)
; - Launcher EXE (OwlangsLauncher.exe) - manages backend and frontend
; - Configuration templates
; - spaCy models (optional, downloaded at runtime)
; Note: Redis is NOT included - desktop version uses in-memory session storage
;
; Why this file may show as modified in git:
; - tools/setup/sync_version.ps1 updates DisplayVersion in this file when syncing version
;   from backend/__init__.py; run it only when you intend to bump version and commit.
; - Build scripts (build_win.ps1, build_win_desktop.ps1) do NOT modify this file; they write
;   to tools/build/installer_generated.nsi and run makensis on that, so builds no longer
;   change this template.

;--------------------------------
; Includes

!include "MUI2.nsh"
!include "FileFunc.nsh"

;--------------------------------
; General

; Name and file
Name "Owlangs"
OutFile "@INSTALLER_OUT@"
; Note: @INSTALLER_OUT@ is replaced by build script with full path including version number

; Default installation directory (x64 Program Files)
InstallDir "$PROGRAMFILES64\Owlangs"

; Request application privileges for Windows Vista/7/8/10/11
RequestExecutionLevel admin

;--------------------------------
; Variables

Var OwlangsConfigDir
Var OwlangsConfigsPath
Var TempInstDir
Var TempConfigsPath
Var ScriptContent

;--------------------------------
; Interface Settings

!define MUI_ABORTWARNING
; Installer and uninstaller icons are injected by build script via @INSTALLER_ICON@ / @INSTALLER_UNICON@
!define MUI_ICON "@INSTALLER_ICON@"
!define MUI_UNICON "@INSTALLER_UNICON@"

;--------------------------------
; Pages

!insertmacro MUI_PAGE_WELCOME
; License page - actual path injected by build script
!insertmacro MUI_PAGE_LICENSE "@LICENSE_FILE@"
!insertmacro MUI_PAGE_COMPONENTS
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_UNPAGE_WELCOME
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_UNPAGE_FINISH

;--------------------------------
; Languages

!insertmacro MUI_LANGUAGE "English"

;--------------------------------
; Installer Sections

Section "Owlangs Translation" SecCore
    SectionIn RO
    SetRegView 64
    
    ; Resolve shared application data directory (C:\ProgramData\Owlangs)
    ; 3rdParty binaries are installed here so pdflatex/pandoc can write at runtime
    ; without requiring admin privileges.
    ExpandEnvStrings $OwlangsConfigDir "%ALLUSERSPROFILE%"
    StrCpy $OwlangsConfigDir "$OwlangsConfigDir\Owlangs"
    StrCpy $OwlangsConfigsPath "$OwlangsConfigDir\configs"
    
    ; Set output path to the installation directory
    SetOutPath "$INSTDIR"
    
    ; Copy all files from package directory (placeholder replaced by build script)
    File /r "@PACKAGE_DIR@"
    
    ; Create configuration directory
    CreateDirectory "$OwlangsConfigDir"
    CreateDirectory "$OwlangsConfigsPath"
    
    ; Create logs directory
    CreateDirectory "$OwlangsConfigDir\logs"
    
    ; Create models directory for spaCy models
    ; Models will be downloaded to C:\ProgramData\Owlangs\models\spacy at runtime
    CreateDirectory "$OwlangsConfigDir\models"
    CreateDirectory "$OwlangsConfigDir\models\spacy"
    
    ; Copy configuration files: FORCE OVERWRITE so that config file version/schema updates
    ; are applied on upgrade. User API keys in secrets.json must be preserved across install/upgrade.
    ; Backup existing secrets.json before copy, then restore after, so keys are never lost.
    StrCpy $TempInstDir "$INSTDIR"
    StrCpy $TempConfigsPath "$OwlangsConfigsPath"
    
    ; Step 1: Backup existing secrets.json (if any) so we can restore after copy
    FileOpen $0 "$TEMP\owlangs_backup_secrets.ps1" w
    FileWrite $0 "$$src = "
    FileWrite $0 '"'
    FileWrite $0 "$OwlangsConfigsPath"
    FileWrite $0 "\secrets.json"
    FileWrite $0 '"'
    FileWrite $0 "$\r$\n"
    FileWrite $0 "$$dest = $\"$TEMP\Owlangs_secrets_backup.json$\"$\r$\n"
    FileWrite $0 "if (Test-Path $$src) { Copy-Item $$src $$dest -Force; Write-Host 'Backed up secrets.json' }$\r$\n"
    FileClose $0
    ExecWait 'powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$TEMP\owlangs_backup_secrets.ps1"' $0
    Delete "$TEMP\owlangs_backup_secrets.ps1"
    
    ; Step 2: Create PowerShell script to copy config files
    ; Split complex strings into parts to avoid NSIS parser issues
    FileOpen $0 "$TEMP\copy_configs.ps1" w
    ; Build line 1: if statement (split to avoid backtick parsing issues)
    FileWrite $0 "if (Test-Path "
    FileWrite $0 '"'
    FileWrite $0 "$TempInstDir"
    FileWrite $0 '\config'
    FileWrite $0 '"'
    FileWrite $0 ") {$\r$\n"
    ; Build line 2: Get-ChildItem
    FileWrite $0 "  Get-ChildItem "
    FileWrite $0 '"'
    FileWrite $0 "$TempInstDir"
    FileWrite $0 '\config'
    FileWrite $0 '"'
    FileWrite $0 " -Recurse -File | ForEach-Object {$\r$\n"
    ; Build line 3: Replace
    FileWrite $0 "    $$dest = $$_.FullName.Replace("
    FileWrite $0 '"'
    FileWrite $0 "$TempInstDir"
    FileWrite $0 '\config'
    FileWrite $0 '"'
    FileWrite $0 ", "
    FileWrite $0 '"'
    FileWrite $0 "$TempConfigsPath"
    FileWrite $0 '"'
    FileWrite $0 ");$\r$\n"
    ; Build line 4: Split-Path
    FileWrite $0 "    $$destDir = Split-Path $$dest -Parent;$\r$\n"
    ; Build line 5: Create directory
    FileWrite $0 "    if (-not (Test-Path $$destDir)) { New-Item -ItemType Directory -Path $$destDir -Force | Out-Null };$\r$\n"
    ; Build line 6: Copy file -Force (overwrite so upgrade gets new config version/schema)
    FileWrite $0 "    Copy-Item $$_.FullName $$dest -Force$\r$\n"
    ; Build line 7: Close ForEach-Object
    FileWrite $0 "  }$\r$\n"
    ; Build line 8: Close if
    FileWrite $0 "}$\r$\n"
    FileClose $0
    ExecWait 'powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$TEMP\copy_configs.ps1"' $0
    Delete "$TEMP\copy_configs.ps1"
    
    ; Step 3: Restore secrets.json so API keys are preserved (package does not include secrets.json)
    FileOpen $0 "$TEMP\owlangs_restore_secrets.ps1" w
    FileWrite $0 "$$backup = $\"$TEMP\Owlangs_secrets_backup.json$\"$\r$\n"
    FileWrite $0 "$$dest = "
    FileWrite $0 '"'
    FileWrite $0 "$OwlangsConfigsPath"
    FileWrite $0 "\secrets.json"
    FileWrite $0 '"'
    FileWrite $0 "$\r$\n"
    FileWrite $0 "if (Test-Path $$backup) { Copy-Item $$backup $$dest -Force; Remove-Item $$backup -Force -ErrorAction SilentlyContinue; Write-Host 'Restored secrets.json (API keys preserved)' }$\r$\n"
    FileClose $0
    ExecWait 'powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$TEMP\owlangs_restore_secrets.ps1"' $0
    Delete "$TEMP\owlangs_restore_secrets.ps1"
    
    ; After copying configs to C:\ProgramData\Owlangs\configs, remove installer-side config
    ; directory so runtime never treats $INSTDIR\config as a project configs dir.
    IfFileExists "$INSTDIR\config\*.*" 0 +2
    RMDir /r "$INSTDIR\config"
    
    ; Create desktop shortcut: OwlangsLauncher when present, else backend exe (Chrome-only build)
    ; Use "all" context so shortcut goes to Public Desktop (visible to all users). When installer
    ; runs as Admin, $DESKTOP otherwise points to Administrator's desktop and the user does not see it.
    ; @BACKEND_EXE_NAME@ is replaced by build script (fixed: Owlangs-win.exe)
    SetShellVarContext all
    IfFileExists "$INSTDIR\launcher\OwlangsLauncher.exe" 0 +3
    CreateShortcut "$DESKTOP\Owlangs.lnk" "$INSTDIR\launcher\OwlangsLauncher.exe" "" "$INSTDIR\launcher\Resources\icon.ico" 0 SW_SHOWNORMAL "" "" "Owlangs - Translation and Collaboration Tool"
    Goto +2
    CreateShortcut "$DESKTOP\Owlangs.lnk" "$INSTDIR\bin\@BACKEND_EXE_NAME@" "" "$INSTDIR\launcher\Resources\icon.ico" 0 SW_SHOWNORMAL "" "" "Owlangs - Translation and Collaboration Tool"
    SetShellVarContext current
    
    ; Create start menu shortcuts (same target as desktop; use "all" so all users see them)
    SetShellVarContext all
    CreateDirectory "$SMPROGRAMS\Owlangs"
    IfFileExists "$INSTDIR\launcher\OwlangsLauncher.exe" 0 +3
    CreateShortcut "$SMPROGRAMS\Owlangs\Owlangs.lnk" "$INSTDIR\launcher\OwlangsLauncher.exe" "" "$INSTDIR\launcher\Resources\icon.ico" 0
    Goto +2
    CreateShortcut "$SMPROGRAMS\Owlangs\Owlangs.lnk" "$INSTDIR\bin\@BACKEND_EXE_NAME@" "" "$INSTDIR\launcher\Resources\icon.ico" 0
    CreateShortcut "$SMPROGRAMS\Owlangs\Uninstall.lnk" "$INSTDIR\uninstall.exe" "" "$INSTDIR\uninstall.exe" 0
    SetShellVarContext current
    
    ; Write registry keys for Add/Remove Programs
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\Owlangs" "DisplayName" "Owlangs"
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\Owlangs" "UninstallString" "$INSTDIR\uninstall.exe"
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\Owlangs" "InstallLocation" "$INSTDIR"
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\Owlangs" "DisplayVersion" "1.2.0.0"
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\Owlangs" "Publisher" "Zampher"
    ; Use main launcher EXE icon as Control Panel icon
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\Owlangs" "DisplayIcon" "$INSTDIR\launcher\OwlangsLauncher.exe"
    WriteRegDWORD HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\Owlangs" "NoModify" 1
    WriteRegDWORD HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\Owlangs" "NoRepair" 1
    
    ; Move 3rdParty from Program Files to ProgramData so pdflatex/pandoc/Redis
    ; can write at runtime without admin privileges.
    ; Use PowerShell because NSIS Rename does not reliably move non-empty directories.
    DetailPrint "Moving 3rdParty to ProgramData..."
    FileOpen $0 "$TEMP\owlangs_move_3rdparty.ps1" w
    FileWrite $0 "$$src = '$INSTDIR\3rdParty'$$\r$$\n"
    FileWrite $0 "$$dst = '$OwlangsConfigDir\3rdParty'$$\r$$\n"
    FileWrite $0 "if (Test-Path $$src) {$$\r$$\n"
    FileWrite $0 "  if (Test-Path $$dst) { Remove-Item $$dst -Recurse -Force }$$\r$$\n"
    FileWrite $0 "  Move-Item $$src $$dst -Force$$\r$$\n"
    FileWrite $0 "  if (Test-Path $$src) { exit 1 } else { exit 0 }$$\r$$\n"
    FileWrite $0 "} else { exit 0 }$$\r$$\n"
    FileClose $0
    ExecWait 'powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$TEMP\owlangs_move_3rdparty.ps1"' $0
    Delete "$TEMP\owlangs_move_3rdparty.ps1"
    IntCmp $0 0 +2
    DetailPrint "WARNING: Failed to move 3rdParty to ProgramData. PDF/Redis features may require admin rights."
    
    ; Create uninstaller
    WriteUninstaller "$INSTDIR\uninstall.exe"
SectionEnd

; Redis Service section removed for desktop version
; Desktop version uses in-memory session storage (REDIS_ENABLED=false)
; No Redis binaries are included in the desktop installer

;--------------------------------
; Descriptions

; Language strings
LangString DESC_SecCore ${LANG_ENGLISH} "Core Owlangs application files (required)"

; Assign language strings to sections
!insertmacro MUI_FUNCTION_DESCRIPTION_BEGIN
  !insertmacro MUI_DESCRIPTION_TEXT ${SecCore} $(DESC_SecCore)
!insertmacro MUI_FUNCTION_DESCRIPTION_END

;--------------------------------
; Uninstaller Section

Section "Uninstall"
    SetRegView 64
    
    ; Stop Redis if running (check in ProgramData 3rdParty directory)
    DetailPrint "Stopping Redis service if running..."
    ; Write a temporary PowerShell script to gracefully stop Redis and force-kill if still running
    FileOpen $0 "$TEMP\owlangs_stop_redis.ps1" w
    ExpandEnvStrings $OwlangsConfigDir "%ALLUSERSPROFILE%"
    StrCpy $OwlangsConfigDir "$OwlangsConfigDir\Owlangs"
    FileWrite $0 "$$redisCli = '$OwlangsConfigDir\3rdParty\windows\Redis-x64-3.0.504\redis-cli.exe'$\r$\n"
    FileWrite $0 "if (-not (Test-Path $$redisCli)) {$\r$\n"
    FileWrite $0 "  $$redisCli = '$OwlangsConfigDir\3rdParty\windows\redis\redis-cli.exe'$\r$\n"
    FileWrite $0 "}$\r$\n"
    FileWrite $0 "if (Test-Path $$redisCli) {$\r$\n"
    FileWrite $0 "  Write-Host 'Stopping Redis gracefully...'$\r$\n"
    FileWrite $0 "  & $$redisCli -h 127.0.0.1 -p 6379 shutdown$\r$\n"
    FileWrite $0 "  Start-Sleep -Seconds 3$\r$\n"
    FileWrite $0 "}$\r$\n"
    FileWrite $0 "$$proc = Get-Process -Name redis-server -ErrorAction SilentlyContinue$\r$\n"
    FileWrite $0 "if ($$proc) {$\r$\n"
    FileWrite $0 "  Write-Host 'Force stopping Redis...'$\r$\n"
    FileWrite $0 "  Stop-Process -Name redis-server -Force -ErrorAction SilentlyContinue$\r$\n"
    FileWrite $0 "  Start-Sleep -Seconds 2$\r$\n"
    FileWrite $0 "}$\r$\n"
    FileClose $0
    ExecWait 'powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$TEMP\owlangs_stop_redis.ps1"' $0
    Delete "$TEMP\owlangs_stop_redis.ps1"
    
    ; Stop Launcher, backend and frontend processes if running
    DetailPrint "Stopping Owlangs processes..."
    ; Use Where-Object with regex because Get-Process -Name does not support wildcards
    ExecWait 'powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "Get-Process | Where-Object { $$_.Name -match \"^(OwlangsLauncher|Owlangs-win|owlangs)$\" } | Stop-Process -Force -ErrorAction SilentlyContinue"' $0
    
    ; Wait a moment for processes to terminate
    Sleep 3000
    
    ; Remove files and directories
    DetailPrint "Removing installation files..."
    RMDir /r "$INSTDIR"
    
    ; Remove 3rdParty binaries from ProgramData (configs/logs/models are kept)
    DetailPrint "Removing 3rdParty binaries..."
    ExpandEnvStrings $OwlangsConfigDir "%ALLUSERSPROFILE%"
    StrCpy $OwlangsConfigDir "$OwlangsConfigDir\Owlangs"
    RMDir /r "$OwlangsConfigDir\3rdParty"
    
    ; Remove shortcuts (created under "all" context = Public Desktop / Public Start Menu)
    DetailPrint "Removing shortcuts..."
    SetShellVarContext all
    Delete "$DESKTOP\Owlangs.lnk"
    RMDir /r "$SMPROGRAMS\Owlangs"
    SetShellVarContext current
    
    ; Remove registry keys
    DetailPrint "Removing registry entries..."
    DeleteRegKey HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\Owlangs"
    
    ; Remove installed config files from C:\ProgramData\Owlangs\configs
    ; but preserve runtime-generated files like secrets.json
    DetailPrint "Removing installed configuration files..."
    ExpandEnvStrings $OwlangsConfigDir "%ALLUSERSPROFILE%"
    StrCpy $OwlangsConfigDir "$OwlangsConfigDir\Owlangs"
    StrCpy $OwlangsConfigsPath "$OwlangsConfigDir\configs"
    
    ; Create PowerShell script to remove installed config files (preserve runtime-generated ones)
    FileOpen $0 "$TEMP\remove_configs.ps1" w
    FileWrite $0 "$$configsPath = "
    FileWrite $0 '"'
    FileWrite $0 "$OwlangsConfigsPath"
    FileWrite $0 '"'
    FileWrite $0 "$\r$\n"
    FileWrite $0 "if (Test-Path $$configsPath) {$\r$\n"
    FileWrite $0 "  $$installedFiles = @('system.json', 'system.json.template', 'platforms.json', 'platforms.json.template', 'ai_platform_status.json', 'ui.json', 'ui.json.template', 'local.json', 'local.json.template', 'app_config.json', 'app_config.json.template', 'local_users.json', 'local_users.json.template')$\r$\n"
    FileWrite $0 "  foreach ($$file in $$installedFiles) {$\r$\n"
    FileWrite $0 "    $$filePath = Join-Path $$configsPath $$file$\r$\n"
    FileWrite $0 "    if (Test-Path $$filePath) {$\r$\n"
    FileWrite $0 "      Remove-Item $$filePath -Force -ErrorAction SilentlyContinue$\r$\n"
    FileWrite $0 "    }$\r$\n"
    FileWrite $0 "  }$\r$\n"
    FileWrite $0 "}$\r$\n"
    FileClose $0
    ExecWait 'powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$TEMP\remove_configs.ps1"' $0
    Delete "$TEMP\remove_configs.ps1"
    
    ; Note: Runtime-generated files (secrets.json, etc.) are NOT removed
    ; to preserve user API keys and other sensitive data
    ; Note: Log files in $OwlangsConfigDir\logs are NOT removed
    ; to preserve log history for troubleshooting
    ; Note: Model files in $OwlangsConfigDir\models are NOT removed
    ; to preserve downloaded spaCy models (they can be large)
    DetailPrint "Uninstallation completed."
    DetailPrint "Note: Runtime-generated config files (secrets.json), logs, and models in C:\ProgramData\Owlangs are preserved."
SectionEnd





















































































