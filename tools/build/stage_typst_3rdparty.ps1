# Stage Typst CLI and offline @preview packages into a 3rdParty tree.
# Usage:
#   tools/build/stage_typst_3rdparty.ps1 -Dest3rdPartyRoot "build\win\Owlangs-1.0\3rdParty" -Fetch

param(
    [Parameter(Mandatory = $true)]
    [string]$Dest3rdPartyRoot,
    [string]$Label = "staging",
    [switch]$Fetch
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RootDir = Split-Path -Parent (Split-Path -Parent $ScriptDir)

function Resolve-FullPath {
    param([string]$Path)
    if (Test-Path -LiteralPath $Path) {
        return (Resolve-Path -LiteralPath $Path).Path
    }
    return [System.IO.Path]::GetFullPath($Path)
}

$repo3rdParty = Join-Path $RootDir "3rdParty"
$resolvedDestRoot = Resolve-FullPath $Dest3rdPartyRoot
$resolvedRepoRoot = Resolve-FullPath $repo3rdParty
$stagingInPlace = (
    $resolvedDestRoot.TrimEnd('\', '/') -eq $resolvedRepoRoot.TrimEnd('\', '/')
)

if ($Fetch) {
    $fetchScript = Join-Path $ScriptDir "fetch_typst_packages.ps1"
    if (Test-Path $fetchScript) {
        Write-Host "[$Label] Fetching Typst @preview packages..." -ForegroundColor Cyan
        & $fetchScript
        if ($LASTEXITCODE -ne 0) {
            Write-Host "[$Label] WARNING: fetch_typst_packages.ps1 failed; offline Typst may require network" -ForegroundColor Yellow
        }
    } else {
        Write-Host "[$Label] WARNING: fetch_typst_packages.ps1 not found" -ForegroundColor Yellow
    }
}

$srcWindows = Join-Path $RootDir "3rdParty\windows"
$destWindows = Join-Path $Dest3rdPartyRoot "windows"
$typstCopied = $false

if (Test-Path $srcWindows) {
    $typstDirs = Get-ChildItem -Path $srcWindows -Directory -Filter "typst*" -ErrorAction SilentlyContinue
    foreach ($d in $typstDirs) {
        $typstExe = Join-Path $d.FullName "typst.exe"
        if (-not (Test-Path $typstExe)) {
            Write-Host "[$Label] WARNING: $($d.Name) exists but typst.exe is missing" -ForegroundColor Yellow
            continue
        }
        $destDir = Join-Path $destWindows $d.Name
        if ($stagingInPlace) {
            Write-Host "[$Label] Typst CLI already in repo 3rdParty: $($d.Name)" -ForegroundColor Green
            $typstCopied = $true
            continue
        }
        New-Item -ItemType Directory -Path $destWindows -Force | Out-Null
        Write-Host "[$Label] Copying Typst CLI: $($d.Name)" -ForegroundColor Green
        Copy-Item -Path $d.FullName -Destination $destDir -Recurse -Force
        $typstCopied = $true
    }
} else {
    Write-Host "[$Label] WARNING: 3rdParty\windows not found; Typst CLI not staged" -ForegroundColor Yellow
}

if (-not $typstCopied) {
    Write-Host "[$Label] WARNING: No typst-* directory under 3rdParty\windows" -ForegroundColor Yellow
}

$srcPackages = Join-Path $RootDir "3rdParty\typst\packages"
$destPackages = Join-Path $Dest3rdPartyRoot "typst\packages"
$cmarkerDir = Join-Path $srcPackages "preview\cmarker\0.1.8"
$mitexDir = Join-Path $srcPackages "preview\mitex\0.2.6"
$packagesReady = (Test-Path $cmarkerDir) -and (Test-Path $mitexDir)

if ($packagesReady) {
    if ($stagingInPlace) {
        Write-Host "[$Label] Typst offline packages already in repo 3rdParty" -ForegroundColor Green
    } else {
        New-Item -ItemType Directory -Path (Split-Path $destPackages -Parent) -Force | Out-Null
        if (Test-Path $destPackages) {
            Remove-Item -Path $destPackages -Recurse -Force
        }
        Write-Host "[$Label] Copying Typst offline packages to $destPackages" -ForegroundColor Green
        Copy-Item -Path $srcPackages -Destination $destPackages -Recurse -Force
    }
} else {
    Write-Host "[$Label] WARNING: Typst offline packages missing under 3rdParty\typst\packages (run fetch_typst_packages.ps1)" -ForegroundColor Yellow
}

# Marker for Inno Setup compile-time #ifexist checks (installer staging only).
if ($Dest3rdPartyRoot -match 'installer_stage') {
    $markerRoot = Split-Path $Dest3rdPartyRoot -Parent
    if ($typstCopied) {
        New-Item -ItemType File -Path (Join-Path $markerRoot ".typst_cli_staged") -Force | Out-Null
    }
    if ($packagesReady) {
        New-Item -ItemType File -Path (Join-Path $markerRoot ".typst_packages_staged") -Force | Out-Null
    }
}
