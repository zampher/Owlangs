# Quick pack: Owlangs Pro edition (Windows desktop, all formats, Pandoc+pdflatex for PDF workflow)
# Usage:
#   tools/build_win_pro.ps1            # simple package (build\win\Owlangs-<version>\)
#   tools/build_win_pro.ps1 -Installer    # Inno Setup installer

param([switch]$Installer)

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RootDir = Split-Path -Parent (Split-Path -Parent $ScriptDir)
Set-Location $RootDir

. "$ScriptDir\verify_build.ps1"

Write-Host "Building Owlangs PRO edition (desktop, Pandoc+pdflatex for PDF/DOCX)..." -ForegroundColor Cyan
# Pro: lite, Windows desktop frontend, IncludePandoc for PDF->DOCX export, no anonymize
if ($Installer) {
    & "$ScriptDir\build_win_installer.ps1" -Lite -Frontend windows -IncludePandoc -Edition Pro
} else {
    & "$ScriptDir\build_win.ps1" --lite -Frontend windows -IncludePandoc -Edition Pro
}
if ($LASTEXITCODE -ne 0) {
    Write-Host "Pro edition build failed (exit $LASTEXITCODE)." -ForegroundColor Red
    exit $LASTEXITCODE
}
if (-not (Test-PackageBuildSuccess -Edition Pro -Installer:$Installer)) {
    Write-Host "Pro edition verification failed." -ForegroundColor Red
    exit 1
}
Write-Host "Pro edition build finished and verified." -ForegroundColor Green
