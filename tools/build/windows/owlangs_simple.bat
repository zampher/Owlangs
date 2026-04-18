@echo off
setlocal

REM Owlangs Simple Launcher
REM Minimal script that just sets environment and runs the executable

REM Set essential environment variables
set OWLANGS_CONFIG_PATH=C:\Users\Public\Owlangs
set DOCUTRANSLATE_PORT=8800

REM Change to executable directory
cd /d "%~dp0bin"

REM Run the executable directly
Owlangs-*-win.exe %*
