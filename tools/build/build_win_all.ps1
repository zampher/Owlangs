# Build Pro and Enterprise editions in one run (Standard skipped: Pro unactivated = Standard).
# Usage:
#   tools/build_win_all.ps1              # simple packages: build\win\Owlangs-<ver>, build\win\Owlangs-full-<ver>
#   tools/build_win_all.ps1 -Installer   # Inno Setup installers (each edition overwrites build\installer\*.exe)
#
# Note: Pro outputs to build\win\Owlangs-<version>. Enterprise outputs to build\win\Owlangs-full-<version>.
# With -Installer, each edition builds one installer exe; the last run (Enterprise) wins in build\installer.

param([switch]$Installer)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RootDir = Split-Path -Parent (Split-Path -Parent $ScriptDir)
Set-Location $RootDir

$results = @{}
$failed = $false

function Run-Edition {
    param([string]$Name, [string]$ScriptName, [switch]$Inst)
    Write-Host ""
    Write-Host "========== $Name ==========" -ForegroundColor Cyan
    $args = @()
    if ($Inst) { $args += "-Installer" }
    & "$ScriptDir\$ScriptName" @args
    $exitCode = $LASTEXITCODE
    $results[$Name] = ($exitCode -eq 0)
    if ($exitCode -ne 0) {
        $script:failed = $true
        Write-Host "========== $Name FAILED (exit $exitCode) ==========" -ForegroundColor Red
        return $exitCode
    }
    Write-Host "========== $Name OK ==========" -ForegroundColor Green
    return 0
}

Write-Host "Building editions (Pro -> Enterprise). Standard skipped (Pro unactivated = Standard)." -ForegroundColor Cyan
if ($Installer) { Write-Host "Mode: Installer (Inno Setup)." -ForegroundColor Cyan }
else { Write-Host "Mode: Simple package (build\win\)." -ForegroundColor Cyan }

$host.UI.WriteLine("DEBUG: Entering build_win_all.ps1 main sequence...")

# Standard edition commented out: Pro build unactivated shows as Standard, so no separate Standard package.
# Run-Edition -Name "Standard"  -ScriptName "build_win_standard.ps1"  -Inst:$Installer
# if (-not $results["Standard"]) {
#     Write-Host "DEBUG: build_win_all.ps1 exiting after Standard (marked FAILED)" -ForegroundColor Red
#     exit 1
# }

Write-Host "DEBUG: Starting Pro edition..." -ForegroundColor Yellow

Run-Edition -Name "Pro"       -ScriptName "build_win_pro.ps1"       -Inst:$Installer
if (-not $results["Pro"]) {
    Write-Host "DEBUG: build_win_all.ps1 exiting after Pro (marked FAILED)" -ForegroundColor Red
    exit 1
}

Write-Host "DEBUG: Starting Enterprise edition..." -ForegroundColor Yellow

Run-Edition -Name "Enterprise" -ScriptName "build_win_enterprise.ps1" -Inst:$Installer
if (-not $results["Enterprise"]) {
    Write-Host "DEBUG: build_win_all.ps1 exiting after Enterprise (marked FAILED)" -ForegroundColor Red
    exit 1
}

# Summary
Write-Host ""
Write-Host "---------- Summary ----------" -ForegroundColor Cyan
foreach ($name in @("Pro", "Enterprise")) {
    $ok = $results[$name]
    $msg = if ($ok) { "OK" } else { "FAILED" }
    $color = if ($ok) { "Green" } else { "Red" }
    Write-Host "  $name : $msg" -ForegroundColor $color
}
Write-Host "------------------------------" -ForegroundColor Cyan
if ($failed) {
    Write-Host "One or more editions failed." -ForegroundColor Red
    exit 1
}
Write-Host "All editions built and verified successfully." -ForegroundColor Green
exit 0
