# CanvasKit 配置验证脚本
# 验证所有 Flutter Web 相关的 index.html 文件是否配置正确

param(
    [switch]$Fix,  # 自动修复发现的问题
    [switch]$Verbose
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RootDir = Split-Path -Parent (Split-Path -Parent $ScriptDir)
Set-Location $RootDir

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "CanvasKit Configuration Verification" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

$filesToCheck = @(
    @{ Path = "frontend\web\index.html"; ExpectedPath = "/canvaskit/"; Description = "Flutter source (development)" },
    @{ Path = "frontend\build\web\index.html"; ExpectedPath = "/canvaskit/"; Description = "Flutter build output" },
    @{ Path = "backend\static\flutter-web\index.html"; ExpectedPath = "/static/flutter-web/canvaskit/"; Description = "Backend static files (production)" }
)

$allPassed = $true

foreach ($fileInfo in $filesToCheck) {
    $filePath = $fileInfo.Path
    $expectedPath = $fileInfo.ExpectedPath
    $description = $fileInfo.Description
    
    Write-Host "Checking: $filePath" -ForegroundColor White
    Write-Host "  Description: $description" -ForegroundColor Gray
    
    if (-not (Test-Path $filePath)) {
        Write-Host "  Status: FILE NOT FOUND" -ForegroundColor Red
        $allPassed = $false
        continue
    }
    
    $content = Get-Content $filePath -Raw
    
    # Check for canvasKitBaseUrl (escaped regex for PowerShell compatibility)
    $ckPattern = "canvasKitBaseUrl:\s*['`"]([^'`"]+)['`"]"
    if ($content -match $ckPattern) {
        $actualPath = $matches[1]
        Write-Host "  CanvasKit Path: $actualPath" -ForegroundColor Gray
        
        if ($actualPath -eq $expectedPath) {
            Write-Host "  Status: ✓ CORRECT" -ForegroundColor Green
        } else {
            Write-Host "  Status: ✗ WRONG (expected: $expectedPath)" -ForegroundColor Red
            $allPassed = $false
            
            if ($Fix) {
                Write-Host "  Fixing..." -ForegroundColor Yellow
                $replacePattern = "canvasKitBaseUrl:\s*['`"][^'`"]+['`"]"
                $newContent = $content -replace $replacePattern, "canvasKitBaseUrl: '$expectedPath'"
                $newContent | Set-Content $filePath -Encoding UTF8
                Write-Host "  Fixed!" -ForegroundColor Green
                $allPassed = $true
            }
        }
    } else {
        Write-Host "  Status: ✗ canvasKitBaseUrl NOT FOUND" -ForegroundColor Red
        $allPassed = $false
        
        if ($Fix) {
            Write-Host "  Attempting to fix..." -ForegroundColor Yellow
            
            # Try to add canvasKitBaseUrl after fontFallbackBaseUrl
            $fbPattern = "(fontFallbackBaseUrl:\s*['`"/\w-]+/,)"
            if ($content -match $fbPattern) {
                $newContent = $content -replace $fbPattern, "`$1`n                canvasKitBaseUrl: '$expectedPath',"
                $newContent | Set-Content $filePath -Encoding UTF8
                Write-Host "  Fixed!" -ForegroundColor Green
                $allPassed = $true
            } else {
                Write-Host "  ERROR: Cannot auto-fix, fontFallbackBaseUrl not found" -ForegroundColor Red
            }
        }
    }
    
    # Check for fontFallbackBaseUrl
    $fbCheckPattern = "fontFallbackBaseUrl:\s*['`"]([^'`"]+)['`"]"
    if ($content -match $fbCheckPattern) {
        $fontPath = $matches[1]
        if ($Verbose) {
            Write-Host "  Font Fallback Path: $fontPath" -ForegroundColor Gray
        }
    } else {
        Write-Host "  WARNING: fontFallbackBaseUrl not found" -ForegroundColor Yellow
    }
    
    # Check for Google CDN references (should not exist without local override)
    if ($content -match "www\.gstatic\.com" -and -not ($content -match "canvasKitBaseUrl")) {
        Write-Host "  WARNING: Google CDN reference without local override" -ForegroundColor Yellow
    }
    
    Write-Host ""
}

# Summary
Write-Host "========================================" -ForegroundColor Cyan
if ($allPassed) {
    Write-Host "✓ All checks passed!" -ForegroundColor Green
} else {
    Write-Host "✗ Some checks failed!" -ForegroundColor Red
    if (-not $Fix) {
        Write-Host "Run with -Fix to automatically fix issues" -ForegroundColor Yellow
    }
    exit 1
}
Write-Host "========================================" -ForegroundColor Cyan
