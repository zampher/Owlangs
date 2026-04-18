# Sync launcher Resources\icon.ico from the canonical Windows ICO (Flutter runner).
# Comments in English per project convention.
param(
    [Parameter(Mandatory = $true)]
    [string]$RootDir
)

$canonicalIcon = Join-Path $RootDir "frontend\windows\runner\resources\app_icon.ico"
$launcherResourcesDir = Join-Path $RootDir "launcher\Resources"
$launcherIconPath = Join-Path $launcherResourcesDir "icon.ico"

New-Item -ItemType Directory -Path $launcherResourcesDir -Force | Out-Null

if (Test-Path $canonicalIcon) {
    Copy-Item $canonicalIcon $launcherIconPath -Force
    Write-Host "[launcher] Synced icon from frontend\windows\runner\resources\app_icon.ico" -ForegroundColor Green
    return $true
}

$rootFavicon = Join-Path $RootDir "favicon.ico"
if (Test-Path $rootFavicon) {
    Copy-Item $rootFavicon $launcherIconPath -Force
    Write-Host "[launcher] Synced icon from repo root favicon.ico (Flutter ICO missing)" -ForegroundColor Yellow
    return $true
}

Write-Host "[launcher] WARNING: No icon source. Run: python tools\generate_ico.py --frontend" -ForegroundColor Yellow
Write-Host "[launcher] WARNING: Expected first: $canonicalIcon" -ForegroundColor Yellow
return $false
