# Download pdfium Windows x64 tarball to 3rdParty/windows for offline Flutter Windows build.
# Run from repo root. After this, run patch_pdfx_for_local_pdfium.ps1 once (after flutter pub get)
# so the pdfx plugin uses the local file instead of downloading at build time.

$ErrorActionPreference = "Stop"
$PDFIUM_VERSION = "7651"
$BaseUrl = "https://github.com/bblanchon/pdfium-binaries/releases/download/chromium/$PDFIUM_VERSION"
$FileName = "pdfium-win-x64.tgz"
$OutName = "pdfium-win-x64-$PDFIUM_VERSION.tgz"
$RootDir = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$OutDir = Join-Path $RootDir "3rdParty\windows"
$OutPath = Join-Path $OutDir $OutName

if (-not (Test-Path $OutDir)) {
    New-Item -ItemType Directory -Path $OutDir -Force | Out-Null
    Write-Host "[pdfium] Created $OutDir" -ForegroundColor Cyan
}

$Url = "$BaseUrl/$FileName"
Write-Host "[pdfium] Downloading $FileName (version $PDFIUM_VERSION) to 3rdParty/windows/..." -ForegroundColor Yellow
try {
    Invoke-WebRequest -Uri $Url -OutFile $OutPath -UseBasicParsing
} catch {
    Write-Host "[pdfium] Download failed: $_" -ForegroundColor Red
    exit 1
}

$size = (Get-Item $OutPath).Length / 1MB
Write-Host "[pdfium] Saved $OutName ($([math]::Round($size, 2)) MB) at $OutPath" -ForegroundColor Green
Write-Host "[pdfium] Run tools\setup\patch_pdfx_for_local_pdfium.ps1 once (after flutter pub get) so the build uses this file." -ForegroundColor Cyan
