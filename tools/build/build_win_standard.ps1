# Quick pack: Owlangs Standard edition (Windows desktop only, basic formats, minimal package)
# Usage:
#   tools/build_win_basic.ps1           # simple package (build\win\Owlangs-<version>\)
#   tools/build_win_basic.ps1 -Installer   # Inno Setup installer

param([switch]$Installer)

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RootDir = Split-Path -Parent (Split-Path -Parent $ScriptDir)
Set-Location $RootDir

. "$ScriptDir\verify_build.ps1"

Write-Host "Building Owlangs STANDARD edition (desktop only, minimal)..." -ForegroundColor Cyan
# Standard: lite, Windows desktop frontend only, no anonymize, no Pandoc
if ($Installer) {
    & "$ScriptDir\build_win_installer.ps1" -Lite -Frontend windows -Edition Standard
} else {
    & "$ScriptDir\build_win.ps1" -Lite -Frontend windows -Edition Standard
}
if ($LASTEXITCODE -ne 0) {
    Write-Host "Standard edition build failed (exit $LASTEXITCODE)." -ForegroundColor Red
    exit $LASTEXITCODE
}
if (-not (Test-PackageBuildSuccess -Edition Standard -Installer:$Installer)) {
    Write-Host "Standard edition verification failed." -ForegroundColor Red
    exit 1
}
Write-Host "Standard edition build finished and verified." -ForegroundColor Green
