# Quick pack: Owlangs Enterprise edition (desktop + Web, full stack, Pandoc+pdflatex)
# Usage:
#   tools/build_win_enterprise.ps1         # simple package (lite + full in build\win\)
#   tools/build_win_enterprise.ps1 -Installer   # Inno Setup installer(s)

param([switch]$Installer)

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RootDir = Split-Path -Parent (Split-Path -Parent $ScriptDir)
Set-Location $RootDir

. "$ScriptDir\verify_build.ps1"

Write-Host "Building Owlangs ENTERPRISE edition (desktop + Web, full, Pandoc)..." -ForegroundColor Cyan
# Enterprise: full build, both frontends (desktop + Chrome/Web), IncludePandoc
if ($Installer) {
    & "$ScriptDir\build_win_installer.ps1" -Full -Frontend both -IncludePandoc -Edition Enterprise
} else {
    & "$ScriptDir\build_win.ps1" --full -Frontend both -IncludePandoc -Edition Enterprise
}
if ($LASTEXITCODE -ne 0) {
    Write-Host "Enterprise edition build failed (exit $LASTEXITCODE)." -ForegroundColor Red
    exit $LASTEXITCODE
}
if (-not (Test-PackageBuildSuccess -Edition Enterprise -Installer:$Installer)) {
    Write-Host "Enterprise edition verification failed." -ForegroundColor Red
    exit 1
}
Write-Host "Enterprise edition build finished and verified." -ForegroundColor Green
