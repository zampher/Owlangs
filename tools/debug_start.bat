@echo off
REM Owlangs 快速调试启动脚本 (Windows)
REM 用于开发环境快速启动应用，支持Redis启用/禁用选择

echo 🚀 Owlangs 调试模式启动脚本
echo ==================================

REM 解析命令行参数
set REDIS_ENABLED=false
if "%1"=="--enable-redis" (
    set REDIS_ENABLED=true
    echo ✅ 已启用Redis (REDIS_ENABLED=true)
) else if "%1"=="--disable-redis" (
    set REDIS_ENABLED=false
    echo ✅ 已禁用Redis (REDIS_ENABLED=false)
) else if "%1"=="" (
    echo ✅ 默认禁用Redis (REDIS_ENABLED=false)
) else (
    echo ❌ 未知参数: %1
    echo.
    echo 用法: %0 [--enable-redis^|--disable-redis]
    echo   --enable-redis   : 启用Redis
    echo   --disable-redis  : 禁用Redis (默认)
    echo   无参数           : 禁用Redis
    echo.
    pause
    exit /b 1
)

echo 当前环境变量: REDIS_ENABLED=%REDIS_ENABLED%

REM 检查是否在正确的目录
if not exist "pyproject.toml" (
    echo ❌ 错误: 请在Owlangs项目根目录下运行此脚本
    echo    当前目录: %CD%
    echo    请切换到项目根目录: cd D:\path\to\Owlangs
    pause
    exit /b 1
)

REM 检查uv是否安装
uv --version >nul 2>&1
if errorlevel 1 (
    echo ❌ 错误: 未找到uv命令
    echo    请先安装uv: https://docs.astral.sh/uv/getting-started/installation/
    pause
    exit /b 1
)

echo 📦 使用uv启动Owlangs...
echo    命令: uv run python -m backend.cli -i
echo    环境: REDIS_ENABLED=%REDIS_ENABLED%
echo.

REM 启动应用
uv run python -m backend.cli -i

REM 保持窗口打开
pause
