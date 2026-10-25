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
REM Owlangs Windows - clear config for fresh reconfigure (customer support)
REM
REM What it clears:
REM   secrets.json, app_config.json, ai_platform_status.json, local.json, ...
REM What it keeps:
REM   platforms.json, system.json, local_users.json (login / platform list)
REM
REM Usage:
REM   clear_owlangs_windows_config.bat
REM   clear_owlangs_windows_config.bat "D:\path\to\templates"
REM
REM Keep this .bat next to clear_owlangs_windows_config.ps1
REM ============================================================================

set "SCRIPT_DIR=%~dp0"
set "PS1=%SCRIPT_DIR%clear_owlangs_windows_config.ps1"
set "TEMPLATE_DIR=%~1"

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
echo  Owlangs 清空配置（重新配置用）
echo ============================================================
echo.
echo  将清空并重建以下运行时配置：
echo    - secrets.json          ^(全部 API Key / Token^)
echo    - app_config.json       ^(界面与翻译偏好^)
echo    - ai_platform_status.json
echo    - local.json / static.json ^(若存在^)
echo.
echo  保留：
echo    - platforms.json / system.json / local_users.json
echo.
call :Warn "注意："
call :Warn "  1) 请先完全退出 Owlangs"
call :Warn "  2) 若提示无权限，请右键“以管理员身份运行”"
call :Warn "  3) 清空前会自动备份到 ProgramData"
call :Warn "  4) 清空后需重新填写 API Key / PaddleOCR Token 等"
echo.

set /p "CONFIRM=输入 CLEAR 继续: "
if /I not "%CONFIRM%"=="CLEAR" (
  echo 已取消。
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
set "BACKUP=%PD%\config_backup_clear_%TS%"

echo.
echo 正在备份到: %BACKUP%
mkdir "%BACKUP%" 2>nul
if errorlevel 1 (
  call :Warn "WARNING: 无法创建备份目录，请尝试管理员运行。"
)

REM Backup whole configs tree when present
if exist "%PD%\configs\" (
  powershell -NoProfile -Command "Copy-Item -LiteralPath '%PD%\configs' -Destination '%BACKUP%\configs' -Recurse -Force -ErrorAction SilentlyContinue"
  echo   backed up: %PD%\configs
)

call :BackupIfExists "%PD%\secrets.json" "%BACKUP%\root_secrets.json"
call :BackupIfExists "%PD%\app_config.json" "%BACKUP%\root_app_config.json"
call :BackupIfExists "%PD%\platforms.json" "%BACKUP%\root_platforms.json"
call :BackupIfExists "%PD%\system.json" "%BACKUP%\root_system.json"
call :BackupIfExists "%LOCALAPPDATA%\Owlangs\configs" "%BACKUP%\localapp_configs"

if defined OWLANGS_CONFIG_PATH (
  if exist "%OWLANGS_CONFIG_PATH%\configs\" (
    powershell -NoProfile -Command "Copy-Item -LiteralPath '%OWLANGS_CONFIG_PATH%\configs' -Destination '%BACKUP%\env_configs' -Recurse -Force -ErrorAction SilentlyContinue"
    echo   backed up: %OWLANGS_CONFIG_PATH%\configs
  )
)

echo.
echo 正在清空配置...
if defined TEMPLATE_DIR (
  powershell -NoProfile -ExecutionPolicy Bypass -File "%PS1%" -BackupDir "%BACKUP%" -TemplateDir "%TEMPLATE_DIR%"
) else (
  powershell -NoProfile -ExecutionPolicy Bypass -File "%PS1%" -BackupDir "%BACKUP%"
)
set "RC=%ERRORLEVEL%"

echo.
if not "%RC%"=="0" (
  call :Warn "ERROR: 清空失败，退出码 %RC%。"
  call :Warn "备份目录: %BACKUP%"
  set "EXIT_CODE=%RC%"
  goto :Finish
)

echo ============================================================
echo  清空完成
echo ============================================================
echo  备份目录:
echo    %BACKUP%
echo.
echo  请客户按以下步骤操作：
echo  1^) 重新启动 Owlangs
echo  2^) 打开 AI 平台设置，重新填写所需 API Key
echo  3^) PaddleOCR Cloud Token 获取地址：
echo     https://aistudio.baidu.com/paddleocr
echo  4^) 先点「测试连接」，通过后再翻译/转换
echo ============================================================
set "EXIT_CODE=0"
goto :Finish

:BackupIfExists
if exist "%~1\" (
  powershell -NoProfile -Command "Copy-Item -LiteralPath '%~1' -Destination '%~2' -Recurse -Force -ErrorAction SilentlyContinue" >nul 2>&1
  if not errorlevel 1 echo   backed up: %~1
  exit /b 0
)
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
REM Versioned names like Owlangs-1.5.9-win.exe
tasklist 2>nul | findstr /I /R /C:"Owlangs.*\.exe" >nul && exit /b 0
exit /b 1

:WaitForOwlangsExit
call :IsOwlangsRunning
if errorlevel 1 exit /b 0
echo.
call :Warn "============================================================"
call :Warn "  检测到 Owlangs 仍在运行。"
call :Warn "  请先完全退出 Owlangs（含托盘图标），再继续。"
call :Warn "============================================================"
:WaitForOwlangsExit_Loop
echo.
call :Warn "当前仍在运行的相关进程："
tasklist 2>nul | findstr /I /R /C:"[Oo]wlangs"
echo.
set /p "WAIT_CHOICE=退出程序后输入 R 重试，或输入 C 取消: "
if /I "%WAIT_CHOICE%"=="C" (
  call :Warn "已取消：请先退出 Owlangs 后再运行本脚本。"
  exit /b 1
)
if /I not "%WAIT_CHOICE%"=="R" (
  call :Warn "请输入 R 或 C。"
  goto :WaitForOwlangsExit_Loop
)
call :IsOwlangsRunning
if errorlevel 1 (
  echo 已确认 Owlangs 退出，继续执行...
  exit /b 0
)
call :Warn "仍检测到 Owlangs 进程，请确认已完全退出。"
goto :WaitForOwlangsExit_Loop

:InitColors
REM ESC/[91m red, ESC/[0m reset (Windows 10+ console)
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
REM Print warning/error line in red. Usage: call :Warn "message"
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
