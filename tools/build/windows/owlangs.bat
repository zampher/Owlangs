@echo off
setlocal

REM Owlangs Lite - Windows Launcher
REM This script sets up the Windows environment and launches Owlangs
REM Note: This script uses RUNTIME configuration files, not template files

REM Set runtime configuration directory for Windows
set OWLANGS_CONFIG_DIR=C:\Users\Public\Owlangs
set OWLANGS_PORT=8800

REM Create config directory if it doesn't exist
if not exist "%OWLANGS_CONFIG_DIR%" (
    mkdir "%OWLANGS_CONFIG_DIR%"
    echo Created configuration directory: %OWLANGS_CONFIG_DIR%
)

REM Verify configuration directory exists (should be created during installation)
if not exist "%OWLANGS_CONFIG_DIR%" (
    echo ERROR: Configuration directory not found: %OWLANGS_CONFIG_DIR%
    echo Please run install.bat first to properly install the application.
    pause
    exit /b 1
)

REM Check if essential configuration files exist (new config structure)
if not exist "%OWLANGS_CONFIG_DIR%\system.json" (
    echo WARNING: system.json not found in configuration directory.
    echo Please ensure the application was properly installed.
)

if not exist "%OWLANGS_CONFIG_DIR%\platforms.json" (
    echo WARNING: platforms.json not found in configuration directory.
    echo Please ensure the application was properly installed.
)

if not exist "%OWLANGS_CONFIG_DIR%\secrets.json" (
    echo WARNING: secrets.json not found in configuration directory.
    echo Please ensure the application was properly installed.
)

REM Set environment variables for the application
set OWLANGS_PORT=%OWLANGS_PORT%
set OWLANGS_CONFIG_PATH=%OWLANGS_CONFIG_DIR%

REM Change to the directory containing the executable
cd /d "%~dp0bin"

REM Find the executable (handle version numbers robustly)
set "EXE_NAME="
set "EXE_PATH="

REM Try to find lite version first
for %%f in (Owlangs-*-win.exe) do (
    if not defined EXE_NAME (
        set "EXE_NAME=%%f"
        set "EXE_PATH=%%~f"
    )
)

REM If not found, try any Owlangs executable
if not defined EXE_NAME (
    for %%f in (Owlangs-*.exe) do (
        if not defined EXE_NAME (
            set "EXE_NAME=%%f"
            set "EXE_PATH=%%~f"
        )
    )
)

REM Check if executable exists and is accessible
if not defined EXE_NAME (
    echo Error: Owlangs executable not found in ^"%cd%^".
    echo Expected: Owlangs-*-win.exe
    echo Please ensure the application is properly installed under ^"%~dp0bin^".
    echo.
    echo Current directory: %cd%
    echo Available files:
    dir /b *.exe 2>nul
    pause
    exit /b 1
)

REM Verify the executable exists and is accessible
if not exist "%EXE_PATH%" (
    echo Error: Owlangs executable not accessible: %EXE_PATH%
    echo Please check file permissions and ensure the file is not corrupted.
    pause
    exit /b 1
)

REM Run the application
echo Starting Owlangs Lite...
echo Configuration directory: %OWLANGS_CONFIG_DIR%
echo Port: %OWLANGS_PORT%
echo Executable: %EXE_NAME%
echo Working directory: %cd%
echo.
echo Press Ctrl+C to stop the application
echo.

REM Set additional environment variables for debugging
set OWLANGS_DEBUG=1

REM Run the executable with -i (interactive/server) and pass through any extra args
"%EXE_NAME%" -i %*
set EXIT_CODE=%errorlevel%

if %EXIT_CODE% neq 0 (
    echo.
    echo Application exited with error code: %EXIT_CODE%
    echo Please check the configuration files and try again.
    echo Configuration directory: %OWLANGS_CONFIG_DIR%
    pause
)
