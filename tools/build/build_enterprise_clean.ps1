# Enterprise 打包脚本（带完整清理）
# 确保使用最新的 Flutter Web 配置

param([switch]$Installer)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RootDir = Split-Path -Parent (Split-Path -Parent $ScriptDir)
Set-Location $RootDir

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Enterprise 打包（完整清理版）" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# 步骤1: 验证 Flutter Web 源文件配置
Write-Host "[1/5] 验证 Flutter Web 配置..." -ForegroundColor Yellow

$indexHtmlPath = "frontend\web\index.html"
if (-not (Test-Path $indexHtmlPath)) {
    Write-Host "ERROR: 找不到 $indexHtmlPath" -ForegroundColor Red
    exit 1
}

$content = Get-Content $indexHtmlPath -Raw
if ($content -match "canvasKitBaseUrl") {
    Write-Host "  ✓ canvasKitBaseUrl 配置已存在" -ForegroundColor Green
    # 显示配置值
    if ($content -match "canvasKitBaseUrl:\s*['\"]([^'\"]+)['\"]") {
        Write-Host "  配置值: $($matches[1])" -ForegroundColor Gray
    }
} else {
    Write-Host "  ✗ 警告: canvasKitBaseUrl 配置不存在!" -ForegroundColor Red
    Write-Host "  正在添加配置..." -ForegroundColor Yellow
    
    # 添加配置
    $newContent = $content -replace "(fontFallbackBaseUrl:\s*['/\w-]+/,)", "`$1`n                // Use local CanvasKit instead of Google CDN`n                canvasKitBaseUrl: '/canvaskit/',"
    
    if ($newContent -ne $content) {
        $newContent | Set-Content $indexHtmlPath -Encoding UTF8
        Write-Host "  ✓ 配置已添加" -ForegroundColor Green
    } else {
        Write-Host "  ✗ 无法自动添加配置，请手动检查" -ForegroundColor Red
        exit 1
    }
}
Write-Host ""

# 步骤2: 彻底清理 Flutter 构建
Write-Host "[2/5] 彻底清理 Flutter 构建..." -ForegroundColor Yellow

$flutterBuildDir = "frontend\build"
if (Test-Path $flutterBuildDir) {
    Write-Host "  删除 $flutterBuildDir..." -ForegroundColor Gray
    Remove-Item -Path $flutterBuildDir -Recurse -Force
    Write-Host "  ✓ Flutter 构建目录已清理" -ForegroundColor Green
} else {
    Write-Host "  无需清理" -ForegroundColor Gray
}

# 同时清理后端静态文件
$backendStaticDir = "backend\static\flutter-web"
if (Test-Path $backendStaticDir) {
    Write-Host "  删除 $backendStaticDir..." -ForegroundColor Gray
    Remove-Item -Path $backendStaticDir -Recurse -Force
    Write-Host "  ✓ 后端静态文件已清理" -ForegroundColor Green
} else {
    Write-Host "  无需清理" -ForegroundColor Gray
}
Write-Host ""

# 步骤3: 验证 canvaskit 目录存在
Write-Host "[3/5] 验证 CanvasKit 文件..." -ForegroundColor Yellow

$canvaskitDir = "frontend\web\canvaskit"
if (Test-Path $canvaskitDir) {
    $canvaskitFiles = Get-ChildItem -Path $canvaskitDir -File | Measure-Object
    Write-Host "  ✓ CanvasKit 源文件存在 ($($canvaskitFiles.Count) 个文件)" -ForegroundColor Green
} else {
    Write-Host "  ✗ 警告: CanvasKit 源文件不存在" -ForegroundColor Red
    Write-Host "  如果构建后 CanvasKit 无法加载，需要手动复制" -ForegroundColor Yellow
}
Write-Host ""

# 步骤4: 执行 Enterprise 构建
Write-Host "[4/5] 执行 Enterprise 构建..." -ForegroundColor Yellow
Write-Host "  调用 build_win_enterprise.ps1..." -ForegroundColor Gray
Write-Host ""

$enterpriseScript = Join-Path $ScriptDir "build_win_enterprise.ps1"
if (-not (Test-Path $enterpriseScript)) {
    Write-Host "ERROR: 找不到 $enterpriseScript" -ForegroundColor Red
    exit 1
}

if ($Installer) {
    & $enterpriseScript -Installer
} else {
    & $enterpriseScript
}

if ($LASTEXITCODE -ne 0) {
    Write-Host "构建失败!" -ForegroundColor Red
    exit $LASTEXITCODE
}
Write-Host ""

# 步骤5: 验证构建结果
Write-Host "[5/5] 验证构建结果..." -ForegroundColor Yellow

# 查找最新的构建目录
$buildWinDir = "build\win"
if (Test-Path $buildWinDir) {
    $latestBuild = Get-ChildItem -Path $buildWinDir -Directory | Sort-Object LastWriteTime -Descending | Select-Object -First 1
    
    if ($latestBuild) {
        $flutterWebDir = Join-Path $latestBuild.FullName "backend\static\flutter-web"
        
        if (-not (Test-Path $flutterWebDir)) {
            # 可能是不同的目录结构
            $flutterWebDir = Join-Path $latestBuild.FullName "static\flutter-web"
        }
        
        if (Test-Path $flutterWebDir) {
            $indexHtmlPath = Join-Path $flutterWebDir "index.html"
            
            if (Test-Path $indexHtmlPath) {
                $content = Get-Content $indexHtmlPath -Raw
                
                if ($content -match "canvasKitBaseUrl") {
                    Write-Host "  ✓ 构建结果包含 canvasKitBaseUrl 配置" -ForegroundColor Green
                } else {
                    Write-Host "  ✗ 错误: 构建结果缺少 canvasKitBaseUrl 配置!" -ForegroundColor Red
                    Write-Host "  文件: $indexHtmlPath" -ForegroundColor Red
                    exit 1
                }
                
                # 检查 canvaskit 目录
                $canvaskitDir = Join-Path $flutterWebDir "canvaskit"
                if (Test-Path $canvaskitDir) {
                    Write-Host "  ✓ CanvasKit 目录存在" -ForegroundColor Green
                } else {
                    Write-Host "  ⚠ 警告: CanvasKit 目录不存在" -ForegroundColor Yellow
                }
            } else {
                Write-Host "  ✗ 错误: 找不到 index.html" -ForegroundColor Red
            }
        } else {
            Write-Host "  ⚠ 警告: 找不到 flutter-web 目录，可能是不同的构建结构" -ForegroundColor Yellow
        }
    } else {
        Write-Host "  ⚠ 警告: 找不到构建目录" -ForegroundColor Yellow
    }
} else {
    Write-Host "  ⚠ 警告: build\win 目录不存在" -ForegroundColor Yellow
}
Write-Host ""

Write-Host "========================================" -ForegroundColor Green
Write-Host "Enterprise 打包完成!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "重要提示:" -ForegroundColor Yellow
Write-Host "  1. 部署后请清除浏览器缓存再测试" -ForegroundColor Cyan
Write-Host "  2. 如果仍有问题，检查浏览器控制台的 CanvasKit 加载路径" -ForegroundColor Cyan
Write-Host "  3. 正确的路径应该是 /canvaskit/ 而不是 www.gstatic.com" -ForegroundColor Cyan
