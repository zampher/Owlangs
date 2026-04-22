# Verify 3rdParty modules in built Windows packages
# Usage:
#   tools/build/verify_3rdparty.ps1              # verify all packages in build\win
#   tools/build/verify_3rdparty.ps1 -PackageDir "build\win\Owlangs-1.2.0.0"

param(
    [string]$PackageDir = ""
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RootDir = Split-Path -Parent (Split-Path -Parent $ScriptDir)
Set-Location $RootDir

function Test-3rdPartyModules {
    param([string]$Dir)

    $issues = @()
    $hasPandoc = $false
    $hasPdflatex = $false
    $hasRedis = $false

    $tpDir = Join-Path $Dir "3rdParty\windows"
    if (-not (Test-Path $tpDir)) {
        $issues += "MISSING: 3rdParty\windows directory not found"
        return $issues
    }

    # Check Pandoc
    $pandocDirs = Get-ChildItem -Path $tpDir -Directory -Filter "pandoc-*" -ErrorAction SilentlyContinue
    if ($pandocDirs) {
        $hasPandoc = $true
        foreach ($d in $pandocDirs) {
            $pandocExe = Join-Path $d.FullName "pandoc.exe"
            if (Test-Path $pandocExe) {
                Write-Host "  OK: Pandoc found: $($d.Name)\pandoc.exe" -ForegroundColor Green
            } else {
                $issues += "WARNING: $($d.Name) exists but pandoc.exe is missing"
            }
        }
    } else {
        $issues += "MISSING: No pandoc-* directory found in 3rdParty\windows"
    }

    # Check pdflatex (XeLaTeX)
    $pdflatexDir = Join-Path $tpDir "pdflatex"
    $xelatexExe = Join-Path $pdflatexDir "bin\windows\xelatex.exe"
    if (Test-Path $xelatexExe) {
        $hasPdflatex = $true
        Write-Host "  OK: pdflatex (XeLaTeX) found: pdflatex\bin\windows\xelatex.exe" -ForegroundColor Green
    } else {
        $issues += "MISSING: pdflatex\bin\windows\xelatex.exe not found"
    }

    # Check Redis
    $redisDir = Join-Path $tpDir "Redis-x64-3.0.504"
    $redisExe = Join-Path $redisDir "redis-server.exe"
    if (Test-Path $redisExe) {
        $hasRedis = $true
        Write-Host "  OK: Redis found: Redis-x64-3.0.504\redis-server.exe" -ForegroundColor Green
    } else {
        $issues += "MISSING: Redis-x64-3.0.504\redis-server.exe not found"
    }

    return $issues
}

$packagesToCheck = @()
if ($PackageDir) {
    $packagesToCheck += $PackageDir
} else {
    $winDir = "build\win"
    if (Test-Path $winDir) {
        $packagesToCheck = Get-ChildItem -Path $winDir -Directory | ForEach-Object { $_.FullName }
    }
}

if ($packagesToCheck.Count -eq 0) {
    Write-Host "No packages found to verify." -ForegroundColor Yellow
    Write-Host "Build a package first with: tools/build/build_win.ps1 -IncludePandoc" -ForegroundColor Yellow
    exit 1
}

$allPassed = $true
foreach ($pkg in $packagesToCheck) {
    $pkgName = Split-Path $pkg -Leaf
    Write-Host "" 
    Write-Host "=== Checking package: $pkgName ===" -ForegroundColor Cyan
    $issues = Test-3rdPartyModules -Dir $pkg
    if ($issues.Count -eq 0) {
        Write-Host "Result: ALL OK" -ForegroundColor Green
    } else {
        $allPassed = $false
        Write-Host "Result: $($issues.Count) issue(s) found" -ForegroundColor Red
        foreach ($issue in $issues) {
            Write-Host "  - $issue" -ForegroundColor Yellow
        }
    }
}

Write-Host ""
if ($allPassed) {
    Write-Host "All packages passed 3rdParty verification." -ForegroundColor Green
    exit 0
} else {
    Write-Host "Some packages are missing required 3rdParty modules." -ForegroundColor Red
    Write-Host "Rebuild with -IncludePandoc to include Pandoc and pdflatex:" -ForegroundColor Yellow
    Write-Host "  tools/build/build_win_pro.ps1" -ForegroundColor Yellow
    exit 1
}
