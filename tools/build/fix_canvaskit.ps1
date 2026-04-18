# Fix CanvasKit path for PyInstaller packaged builds
# Usage: tools/build/fix_canvaskit.ps1 -BackendStaticDir "backend\static\flutter-web"

param(
    [Parameter(Mandatory=$true)]
    [string]$BackendStaticDir
)

$ErrorActionPreference = "Stop"

Write-Host "[canvaskit-fix] Fixing CanvasKit paths in $BackendStaticDir..." -ForegroundColor Cyan

# Ensure directory exists
if (-not (Test-Path $BackendStaticDir)) {
    Write-Host "[canvaskit-fix] ERROR: Directory not found: $BackendStaticDir" -ForegroundColor Red
    exit 1
}

# Fix index.html base href and CanvasKit path
$indexHtmlPath = Join-Path $BackendStaticDir "index.html"
if (Test-Path $indexHtmlPath) {
    Write-Host "[canvaskit-fix] Fixing base href and CanvasKit path in index.html..." -ForegroundColor Yellow
    $content = Get-Content -Path $indexHtmlPath -Raw
    
    # Replace various possible base href formats
    $content = $content -replace '<base href="/">', '<base href="/static/flutter-web/">'
    $content = $content -replace '<base href="\$FLUTTER_BASE_HREF">', '<base href="/static/flutter-web/">'
    $content = $content -replace '<base href="">', '<base href="/static/flutter-web/">'
    # Also handle single quotes just in case
    $content = $content -replace "<base href='/'>", '<base href="/static/flutter-web/">'
    $content = $content -replace "<base href='\`$FLUTTER_BASE_HREF'>", '<base href="/static/flutter-web/">'
    
    # Fix CanvasKit base URL to use local path
    $content = $content -replace "canvasKitBaseUrl:\s*'/canvaskit/'", "canvasKitBaseUrl: '/static/flutter-web/canvaskit/'"
    $content = $content -replace 'canvasKitBaseUrl:\s*"/canvaskit/"', "canvasKitBaseUrl: '/static/flutter-web/canvaskit/'"
    
    Set-Content -Path $indexHtmlPath -Value $content -NoNewline
    Write-Host "[canvaskit-fix] Base href fixed to /static/flutter-web/" -ForegroundColor Green
    
    # Verify the fix
    $verifyContent = Get-Content -Path $indexHtmlPath -Raw
    if ($verifyContent -match '<base href="/static/flutter-web/">') {
        Write-Host "[canvaskit-fix] ✓ Verified: base href is correct" -ForegroundColor Green
    } else {
        Write-Host "[canvaskit-fix] ⚠ Warning: base href fix may not have applied correctly" -ForegroundColor Yellow
    }
    
    # Verify CanvasKit path
    if ($verifyContent -match "canvasKitBaseUrl:\s*'/static/flutter-web/canvaskit/'") {
        Write-Host "[canvaskit-fix] ✓ Verified: CanvasKit path is correct" -ForegroundColor Green
    } else {
        Write-Host "[canvaskit-fix] ⚠ Warning: CanvasKit path may not be correct" -ForegroundColor Yellow
    }
} else {
    Write-Host "[canvaskit-fix] WARNING: index.html not found at $indexHtmlPath" -ForegroundColor Yellow
}

# Verify CanvasKit directory exists
$canvaskitDir = Join-Path $BackendStaticDir "canvaskit"
if (Test-Path $canvaskitDir) {
    $canvaskitFiles = (Get-ChildItem -Path $canvaskitDir -Recurse -File).Count
    Write-Host "[canvaskit-fix] ✓ CanvasKit directory exists with $canvaskitFiles files" -ForegroundColor Green
} else {
    Write-Host "[canvaskit-fix] ⚠ Warning: CanvasKit directory not found at $canvaskitDir" -ForegroundColor Yellow
    Write-Host "[canvaskit-fix]   The app will use HTML renderer instead (slower but works)" -ForegroundColor Yellow
}

Write-Host "[canvaskit-fix] CanvasKit fix completed." -ForegroundColor Green
