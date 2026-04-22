@echo off
setlocal

REM Owlangs Full - Windows Launcher
REM This script sets up the Windows environment and launches Owlangs Full

REM Set default configuration directory for Windows
set OWLANGS_CONFIG_DIR=C:\ProgramData\Owlangs
set OWLANGS_PORT=8800

REM Create config directory if it doesn't exist
if not exist "%OWLANGS_CONFIG_DIR%" (
    mkdir "%OWLANGS_CONFIG_DIR%"
    echo Created configuration directory: %OWLANGS_CONFIG_DIR%
)

REM Copy template files to config directory if they don't exist (new config structure)
if not exist "%OWLANGS_CONFIG_DIR%\system.json" (
    if exist "%~dp0config\system.json.template" (
        copy "%~dp0config\system.json.template" "%OWLANGS_CONFIG_DIR%\system.json"
        echo Created system.json from template
    )
)

if not exist "%OWLANGS_CONFIG_DIR%\platforms.json" (
    if exist "%~dp0config\platforms.json.template" (
        copy "%~dp0config\platforms.json.template" "%OWLANGS_CONFIG_DIR%\platforms.json"
        echo Created platforms.json from template
    )
)

if not exist "%OWLANGS_CONFIG_DIR%\ui.json" (
    if exist "%~dp0config\ui.json.template" (
        copy "%~dp0config\ui.json.template" "%OWLANGS_CONFIG_DIR%\ui.json"
        echo Created ui.json from template
    )
)

if not exist "%OWLANGS_CONFIG_DIR%\secrets.json" (
    if exist "%~dp0config\secrets.json.template" (
        copy "%~dp0config\secrets.json.template" "%OWLANGS_CONFIG_DIR%\secrets.json"
        echo Created secrets.json from template
    )
)

if not exist "%OWLANGS_CONFIG_DIR%\local.json" (
    if exist "%~dp0config\local.json.template" (
        copy "%~dp0config\local.json.template" "%OWLANGS_CONFIG_DIR%\local.json"
        echo Created local.json from template
    )
)

if not exist "%OWLANGS_CONFIG_DIR%\app_config.json" (
    if exist "%~dp0config\app_config.json.template" (
        copy "%~dp0config\app_config.json.template" "%OWLANGS_CONFIG_DIR%\app_config.json"
    ) else if exist "%~dp0config\app_config.json" (
        copy "%~dp0config\app_config.json" "%OWLANGS_CONFIG_DIR%\"
    )
    echo Copied app_config.json to %OWLANGS_CONFIG_DIR%
)

REM Deploy pdflatex (TinyTeX/XeLaTeX) to ProgramData if bundled in the package.
REM This ensures PDF export works even when the application is placed in a
REM read-only location such as C:\Program Files.
set "PDLATEX_SRC=%~dp03rdParty\windows\pdflatex"
set "PDLATEX_DST=%OWLANGS_CONFIG_DIR%\3rdParty\windows\pdflatex"
if exist "%PDLATEX_SRC%\bin\windows\xelatex.exe" (
    if not exist "%PDLATEX_DST%\bin\windows\xelatex.exe" (
        echo Deploying pdflatex to ProgramData for write access...
        powershell -NoProfile -Command "Copy-Item -Path '%PDLATEX_SRC%' -Destination '%PDLATEX_DST%' -Recurse -Force -ErrorAction SilentlyContinue"
        if exist "%PDLATEX_DST%\bin\windows\xelatex.exe" (
            echo pdflatex deployed to %PDLATEX_DST%
        ) else (
            echo WARNING: Failed to deploy pdflatex to ProgramData. PDF export may require admin rights.
        )
    )
)

REM Set environment variables for the application
set DOCUTRANSLATE_PORT=%OWLANGS_PORT%
set OWLANGS_CONFIG_PATH=%OWLANGS_CONFIG_DIR%

REM Change to the directory containing the executable
cd /d "%~dp0bin"

REM Check if executable exists
if not exist "Owlangs-*-win.exe" (
    echo Error: Owlangs backend executable not found in bin directory
    echo Please ensure the application is properly installed
    pause
    exit /b 1
)

REM Find the executable (handle version numbers)
for %%f in (Owlangs-*-win.exe) do set EXE_NAME=%%f

REM Run the application with -i (interactive/server) and pass through any extra args
echo Starting Owlangs...
echo Configuration directory: %OWLANGS_CONFIG_DIR%
echo Port: %OWLANGS_PORT%
echo Executable: %EXE_NAME%
echo.
"%EXE_NAME%" -i %*
