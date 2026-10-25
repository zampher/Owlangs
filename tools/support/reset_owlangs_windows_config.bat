@echo off
setlocal EnableExtensions EnableDelayedExpansion

REM Keep console open when double-clicked (explorer starts cmd /c which auto-closes).
if /I not "%OWLANGS_SUPPORT_INNER%"=="1" (
  set "OWLANGS_SUPPORT_INNER=1"
  cmd /k call "%~f0" %*
  exit /b %ERRORLEVEL%
)

chcp 65001 >nul

REM ============================================================================
REM Owlangs Windows config reset (customer support)
REM
REM Usage:
REM   reset_owlangs_windows_config.bat           Clear PaddleOCR keys only
REM   reset_owlangs_windows_config.bat full      Reset ALL API keys in secrets.json
REM
REM Keep this .bat next to reset_owlangs_windows_config.ps1
REM ============================================================================

set "MODE=paddle"
if /I "%~1"=="full" set "MODE=full"
if /I "%~1"=="/full" set "MODE=full"

set "SCRIPT_DIR=%~dp0"
set "PS1=%SCRIPT_DIR%reset_owlangs_windows_config.ps1"
set "EXIT_CODE=0"
call :InitColors

if not exist "%PS1%" (
  call :Warn "ERROR: Missing companion script:"
  call :Warn "  %PS1%"
  set "EXIT_CODE=1"
  goto :Finish
)

echo.
echo ============================================================
echo  Owlangs Windows config reset
echo ============================================================
echo.
echo  Mode: %MODE%
if /I "%MODE%"=="paddle" (
  echo  - Clear PaddleOCR Cloud / Local API keys only
  echo  - Other LLM / MinerU keys are kept
) else (
  echo  - Reset ALL platform API keys in secrets.json
  echo  - Other settings files are kept ^(backed up^)
)
echo.
call :Warn "IMPORTANT:"
call :Warn "  1) Fully quit Owlangs before continuing."
call :Warn "  2) Run as Administrator if ProgramData write is denied."
call :Warn "  3) Clearing local config alone will NOT fix a bad/expired"
call :Warn "     Baidu AI Studio token. After reset, paste a NEW token"
call :Warn "     from: https://aistudio.baidu.com/paddleocr"
echo.

set /p "CONFIRM=Type YES to continue: "
if /I not "%CONFIRM%"=="YES" (
  echo Cancelled.
  set "EXIT_CODE=1"
  goto :Finish
)

call :WaitForOwlangsExit
if errorlevel 1 (
  set "EXIT_CODE=1"
  goto :Finish
)

set "TS="
for /f %%i in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd_HHmmss"') do set "TS=%%i"
if not defined TS set "TS=manual"

set "PD=%ProgramData%\Owlangs"
set "BACKUP=%PD%\config_backup_%TS%"

echo.
echo Creating backup: %BACKUP%
mkdir "%BACKUP%" 2>nul
if errorlevel 1 (
  call :Warn "WARNING: Could not create %BACKUP%"
  call :Warn "Try running this script as Administrator."
)

call :BackupIfExists "%PD%\secrets.json" "%BACKUP%\root_secrets.json"
call :BackupIfExists "%PD%\app_config.json" "%BACKUP%\root_app_config.json"
call :BackupIfExists "%PD%\platforms.json" "%BACKUP%\root_platforms.json"
call :BackupIfExists "%PD%\system.json" "%BACKUP%\root_system.json"
call :BackupIfExists "%PD%\ai_platform_status.json" "%BACKUP%\root_ai_platform_status.json"
call :BackupIfExists "%PD%\configs\secrets.json" "%BACKUP%\configs_secrets.json"
call :BackupIfExists "%PD%\configs\app_config.json" "%BACKUP%\configs_app_config.json"
call :BackupIfExists "%PD%\configs\platforms.json" "%BACKUP%\configs_platforms.json"
call :BackupIfExists "%PD%\configs\system.json" "%BACKUP%\configs_system.json"
call :BackupIfExists "%PD%\configs\ai_platform_status.json" "%BACKUP%\configs_ai_platform_status.json"
call :BackupIfExists "%LOCALAPPDATA%\Owlangs\configs\secrets.json" "%BACKUP%\localapp_secrets.json"
call :BackupIfExists "%LOCALAPPDATA%\Owlangs\configs\app_config.json" "%BACKUP%\localapp_app_config.json"

if defined OWLANGS_CONFIG_PATH (
  call :BackupIfExists "%OWLANGS_CONFIG_PATH%\secrets.json" "%BACKUP%\env_secrets.json"
  call :BackupIfExists "%OWLANGS_CONFIG_PATH%\configs\secrets.json" "%BACKUP%\env_configs_secrets.json"
  call :BackupIfExists "%OWLANGS_CONFIG_PATH%\app_config.json" "%BACKUP%\env_app_config.json"
  call :BackupIfExists "%OWLANGS_CONFIG_PATH%\configs\app_config.json" "%BACKUP%\env_configs_app_config.json"
)

echo.
echo Applying reset...
powershell -NoProfile -ExecutionPolicy Bypass -File "%PS1%" -Mode "%MODE%" -BackupDir "%BACKUP%"
set "RC=%ERRORLEVEL%"

echo.
if not "%RC%"=="0" (
  call :Warn "ERROR: Reset finished with code %RC%."
  call :Warn "Backup (if created): %BACKUP%"
  set "EXIT_CODE=%RC%"
  goto :Finish
)

echo ============================================================
echo  Reset finished.
echo ============================================================
echo  Backup folder:
echo    %BACKUP%
echo.
echo  Next steps:
echo  1^) Start Owlangs
echo  2^) AI Platform Settings -^> PaddleOCR ^(Cloud^)
echo  3^) Paste a NEW token from https://aistudio.baidu.com/paddleocr
echo  4^) Test Connection, then retry conversion
echo.
call :Warn "If still 401: Baidu is rejecting the token itself"
call :Warn "(wrong product key / expired / no permission)."
echo ============================================================
set "EXIT_CODE=0"
goto :Finish

:BackupIfExists
if exist "%~1" (
  copy /Y "%~1" "%~2" >nul
  if not errorlevel 1 echo   backed up: %~1
)
exit /b 0

:IsOwlangsRunning
REM Returns 0 if Owlangs process is running, 1 if not.
tasklist /FI "IMAGENAME eq owlangs.exe" 2>nul | find /I "owlangs.exe" >nul && exit /b 0
tasklist /FI "IMAGENAME eq Owlangs-win.exe" 2>nul | find /I "Owlangs-win.exe" >nul && exit /b 0
tasklist /FI "IMAGENAME eq OwlangsLauncher.exe" 2>nul | find /I "OwlangsLauncher.exe" >nul && exit /b 0
tasklist 2>nul | findstr /I /R /C:"Owlangs.*\.exe" >nul && exit /b 0
exit /b 1

:WaitForOwlangsExit
call :IsOwlangsRunning
if errorlevel 1 exit /b 0
echo.
call :Warn "============================================================"
call :Warn "  Owlangs is still running."
call :Warn "  Please fully quit Owlangs first (including tray icon)."
call :Warn "============================================================"
:WaitForOwlangsExit_Loop
echo.
call :Warn "Running Owlangs-related processes:"
tasklist 2>nul | findstr /I /R /C:"[Oo]wlangs"
echo.
set /p "WAIT_CHOICE=After quitting, type R to retry, or C to cancel: "
if /I "%WAIT_CHOICE%"=="C" (
  call :Warn "Cancelled: quit Owlangs before running this script."
  exit /b 1
)
if /I not "%WAIT_CHOICE%"=="R" (
  call :Warn "Please type R or C."
  goto :WaitForOwlangsExit_Loop
)
call :IsOwlangsRunning
if errorlevel 1 (
  echo Owlangs has exited. Continuing...
  exit /b 0
)
call :Warn "Owlangs is still running. Please quit it completely."
goto :WaitForOwlangsExit_Loop

:InitColors
for /F %%A in ('powershell -NoProfile -Command "[char]27"') do set "ESC=%%A"
if not defined ESC (
  set "RED="
  set "RST="
  exit /b 0
)
set "RED=%ESC%[91m"
set "RST=%ESC%[0m"
exit /b 0

:Warn
set "WARN_MSG=%~1"
powershell -NoProfile -Command "Write-Host $env:WARN_MSG -ForegroundColor Red"
set "WARN_MSG="
exit /b 0

:Finish
echo.
echo ============================================================
echo  执行结束。请查看上方输出。
echo  可直接关闭本窗口，或输入 exit 后回车退出。
echo ============================================================
if not defined EXIT_CODE set "EXIT_CODE=0"
exit /b %EXIT_CODE%
