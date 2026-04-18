# Build Flutter Web for Chrome / browser
# Compiles the frontend and optionally copies to backend/static/flutter-web.
# Use this when you only need the web build (e.g. for Chrome testing or backend serving).
#
# Usage:
#   tools/build_flutter_chrome.ps1              # build + copy to backend
#   tools/build_flutter_chrome.ps1 -NoCopy      # build only, do not copy
#   tools/build_flutter_chrome.ps1 -OpenChrome  # build, copy, then open Chrome to local server
#   tools/build_flutter_chrome.ps1 -NoClean     # skip flutter clean (faster rebuild)

param(
    [switch]$NoCopy,
    [switch]$OpenChrome,
    [switch]$NoClean
)

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RootDir = Split-Path -Parent (Split-Path -Parent $ScriptDir)
Set-Location $RootDir

$frontendDir = "frontend"
if (-not (Test-Path $frontendDir)) {
    Write-Host "[build_flutter_chrome] ERROR: frontend directory not found." -ForegroundColor Red
    exit 1
}

Push-Location $frontendDir
try {
    if (-not $NoClean) {
        Write-Host "[frontend] Running: flutter clean" -ForegroundColor Yellow
        flutter clean
        if ($LASTEXITCODE -ne 0) {
            Write-Host "[frontend] ERROR: flutter clean failed!" -ForegroundColor Red
            exit 1
        }
    }

    Write-Host "[frontend] Running: flutter pub get" -ForegroundColor Yellow
    flutter pub get
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[frontend] ERROR: flutter pub get failed!" -ForegroundColor Red
        exit 1
    }

    Write-Host "[frontend] Running: flutter build web --release --no-tree-shake-icons" -ForegroundColor Yellow
    flutter build web --release --no-tree-shake-icons
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[frontend] ERROR: Flutter Web build failed!" -ForegroundColor Red
        exit 1
    }

    # Copy fonts to build output (match build_win_web.ps1)
    $buildFontsDir = "build\web\assets\fonts"
    if (-not (Test-Path $buildFontsDir)) {
        New-Item -ItemType Directory -Path $buildFontsDir -Force | Out-Null
    }
    $sourceFontsDir = "fonts"
    if (Test-Path $sourceFontsDir) {
        Write-Host "[frontend] Copying fonts to build output..." -ForegroundColor Yellow
        Get-ChildItem -Path $sourceFontsDir -File | ForEach-Object {
            Copy-Item -Path $_.FullName -Destination (Join-Path $buildFontsDir $_.Name) -Force
        }
    }

    if (-not $NoCopy) {
        $backendStaticDir = "..\backend\static\flutter-web"
        Write-Host "[frontend] Copying build output to $backendStaticDir..." -ForegroundColor Yellow
        New-Item -ItemType Directory -Path $backendStaticDir -Force | Out-Null
        Copy-Item -Path "build\web\*" -Destination $backendStaticDir -Recurse -Force
        Write-Host "[frontend] Flutter Web built and copied to backend." -ForegroundColor Green
    } else {
        Write-Host "[frontend] Flutter Web built (not copied). Output: frontend\build\web\" -ForegroundColor Green
    }

    if ($OpenChrome) {
        $serveDir = if ($NoCopy) { (Join-Path $RootDir "frontend\build\web") } else { (Join-Path $RootDir "backend\static\flutter-web") }
        $port = 8080
        Write-Host "[frontend] Starting HTTP server on port $port..." -ForegroundColor Yellow
        $job = Start-Job -ScriptBlock {
            param($dir, $p)
            Set-Location $dir
            python -m http.server $p
        } -ArgumentList $serveDir, $port
        Start-Sleep -Seconds 2
        $url = "http://localhost:$port"
        Write-Host "[frontend] Opening Chrome: $url" -ForegroundColor Cyan
        Start-Process "chrome" -ArgumentList $url -ErrorAction SilentlyContinue
        if (-not $?) {
            Start-Process "msedge" -ArgumentList $url -ErrorAction SilentlyContinue
        }
        Write-Host "[frontend] Press Enter to stop the server..." -ForegroundColor Gray
        Read-Host
        Stop-Job $job
        Remove-Job $job
    }
} finally {
    Pop-Location
}
