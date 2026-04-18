# Build Flutter Web with correct flags
# This script ensures icons are properly included and IconData issues are avoided

Write-Host "🔨 Building Flutter Web..." -ForegroundColor Cyan

# Build with --no-tree-shake-icons to avoid IconData constant issues
flutter build web --release --no-tree-shake-icons

if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ Flutter Web build successful!" -ForegroundColor Green
    
    # Verify icons were copied to build output
    Write-Host "`n📋 Checking build output..." -ForegroundColor Yellow
    if (Test-Path "build\web\favicon.ico") {
        Write-Host "  ✅ favicon.ico copied" -ForegroundColor Green
    } else {
        Write-Host "  ⚠️ favicon.ico not found in build output" -ForegroundColor Yellow
    }
    
    if (Test-Path "build\web\icons") {
        $iconCount = (Get-ChildItem "build\web\icons" -File).Count
        Write-Host "  ✅ icons directory exists ($iconCount files)" -ForegroundColor Green
    } else {
        Write-Host "  ⚠️ icons directory not found in build output" -ForegroundColor Yellow
    }
    
    Write-Host "`n📦 Next step: Copy to backend" -ForegroundColor Cyan
    Write-Host "  Run: Copy-Item -Path 'build\web\*' -Destination '..\backend\static\flutter-web\' -Recurse -Force" -ForegroundColor Gray
} else {
    Write-Host "❌ Build failed!" -ForegroundColor Red
    exit 1
}

