# Fetch Typst @preview packages (cmarker, mitex) into 3rdParty for offline builds.
# Usage:
#   tools/build/fetch_typst_packages.ps1
#
# Requires network on first run. Re-run is a no-op when packages already exist.

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RootDir = Split-Path -Parent (Split-Path -Parent $ScriptDir)
Set-Location $RootDir

$PackagesDir = Join-Path $RootDir "3rdParty\typst\packages"
$CmarkerDir = Join-Path $PackagesDir "preview\cmarker\0.1.8"
$MitexDir = Join-Path $PackagesDir "preview\mitex\0.2.6"

function Test-TypstPackagesComplete {
    return (Test-Path $CmarkerDir) -and (Test-Path $MitexDir)
}

if (Test-TypstPackagesComplete) {
    Write-Host "[typst-packages] Already present under $PackagesDir" -ForegroundColor Green
    exit 0
}

$TypstBin = $null
$tpWindows = Join-Path $RootDir "3rdParty\windows"
if (Test-Path $tpWindows) {
    $typstDirs = Get-ChildItem -Path $tpWindows -Directory -Filter "typst*" |
        Sort-Object Name -Descending
    foreach ($d in $typstDirs) {
        $exe = Join-Path $d.FullName "typst.exe"
        if (Test-Path $exe) {
            $TypstBin = $exe
            break
        }
    }
}
if (-not $TypstBin) {
    $cmd = Get-Command typst -ErrorAction SilentlyContinue
    if ($cmd) { $TypstBin = $cmd.Source }
}
if (-not $TypstBin) {
    Write-Error "Typst CLI not found. Place typst under 3rdParty\windows\typst-* or install on PATH."
}

Write-Host "[typst-packages] Using Typst: $TypstBin" -ForegroundColor Cyan
Write-Host "[typst-packages] Downloading @preview packages to $PackagesDir ..." -ForegroundColor Cyan

New-Item -ItemType Directory -Path $PackagesDir -Force | Out-Null

$tempDir = Join-Path $env:TEMP "owlangs_typst_fetch_$([Guid]::NewGuid().ToString('N'))"
New-Item -ItemType Directory -Path $tempDir -Force | Out-Null

try {
    $typFile = Join-Path $tempDir "fetch_packages.typ"
    @'
#import "@preview/cmarker:0.1.8"
#import "@preview/mitex:0.2.6": mitex
'@ | Set-Content -Path $typFile -Encoding UTF8

    $pdfOut = Join-Path $tempDir "fetch_packages.pdf"
    $env:TYPST_PACKAGE_CACHE_PATH = $PackagesDir
    & $TypstBin compile $typFile $pdfOut
    if ($LASTEXITCODE -ne 0) {
        throw "typst compile failed with exit code $LASTEXITCODE"
    }

    if (-not (Test-TypstPackagesComplete)) {
        throw "Typst compile succeeded but required packages are missing under $PackagesDir"
    }

    Write-Host "[typst-packages] OK: cmarker + mitex cached for offline use" -ForegroundColor Green
}
finally {
    Remove-Item -Path $tempDir -Recurse -Force -ErrorAction SilentlyContinue
    Remove-Item Env:TYPST_PACKAGE_CACHE_PATH -ErrorAction SilentlyContinue
}

exit 0
