# 修复 CanvasKit 路径（用于部署后修复）
# 如果部署后发现 CanvasKit 仍从 Google CDN 加载，运行此脚本

param(
    [string]$PackageDir = ""  # 打包后的目录路径，如 build\win\Owlangs-1.2.0.0
)

$ErrorActionPreference = "Stop"

Write-Host "CanvasKit 路径修复工具" -ForegroundColor Cyan
Write-Host "======================" -ForegroundColor Cyan
Write-Host ""

# 如果没有指定目录，查找最新的构建目录
if (-not $PackageDir) {
    $buildWinDir = "build\win"
    if (Test-Path $buildWinDir) {
        $latestBuild = Get-ChildItem -Path $buildWinDir -Directory | Sort-Object LastWriteTime -Descending | Select-Object -First 1
        if ($latestBuild) {
            $PackageDir = $latestBuild.FullName
            Write-Host "自动检测到最新构建: $PackageDir" -ForegroundColor Yellow
        }
    }
}

if (-not $PackageDir -or -not (Test-Path $PackageDir)) {
    Write-Host "错误: 找不到构建目录" -ForegroundColor Red
    Write-Host "用法: .\fix_canvaskit_path.ps1 -PackageDir 'build\win\Owlangs-x.x.x.x'" -ForegroundColor Yellow
    exit 1
}

# 查找所有 index.html 文件
$indexFiles = Get-ChildItem -Path $PackageDir -Filter "index.html" -Recurse

if (-not $indexFiles) {
    Write-Host "错误: 找不到任何 index.html 文件" -ForegroundColor Red
    exit 1
}

Write-Host "找到 $($indexFiles.Count) 个 index.html 文件" -ForegroundColor Green
Write-Host ""

$fixedCount = 0
foreach ($file in $indexFiles) {
    Write-Host "处理: $($file.FullName)" -ForegroundColor Gray
    
    $content = Get-Content $file.FullName -Raw
    $originalContent = $content
    
    # 检查是否使用了 Google CDN
    if ($content -match "www\.gstatic\.com/flutter-canvaskit") {
        Write-Host "  ⚠ 发现 Google CDN 引用" -ForegroundColor Yellow
        
        # 确定正确的 CanvasKit 路径
        # 如果文件在 backend/static/flutter-web/ 下，使用 /static/flutter-web/canvaskit/
        # 如果文件在其他位置，使用相对路径或 /canvaskit/
        
        if ($file.FullName -match "backend\\static\\flutter-web") {
            # 后端静态文件路径 - 使用绝对路径
            $content = $content -replace "canvasKitBaseUrl:\s*'/canvaskit/'", "canvasKitBaseUrl: '/static/flutter-web/canvaskit/'"
            $content = $content -replace 'canvasKitBaseUrl:\s*"/canvaskit/"', "canvasKitBaseUrl: '/static/flutter-web/canvaskit/'"
            
            # 如果没有配置，添加它
            if (-not ($content -match "canvasKitBaseUrl")) {
                $content = $content -replace "(initializeEngine\(\{[^}]*?)\}", "`$1,`n                canvasKitBaseUrl: '/static/flutter-web/canvaskit/'`n              }"
            }
            
            # 如果没有 fontFallbackBaseUrl，也添加它
            if (-not ($content -match "fontFallbackBaseUrl")) {
                $content = $content -replace "(canvasKitBaseUrl:[^}]+\})", "`$1,`n                fontFallbackBaseUrl: '/no-cdn-fonts/'"
            }
        } else {
            # 其他路径，使用相对路径
            $content = $content -replace "canvasKitBaseUrl:\s*'/canvaskit/'", "canvasKitBaseUrl: 'canvaskit/'"
            $content = $content -replace 'canvasKitBaseUrl:\s*"/canvaskit/"', "canvasKitBaseUrl: 'canvaskit/'"
            
            # 如果没有配置，添加它
            if (-not ($content -match "canvasKitBaseUrl")) {
                $content = $content -replace "(initializeEngine\(\{[^}]*?)\}", "`$1,`n                canvasKitBaseUrl: 'canvaskit/',`n                fontFallbackBaseUrl: '/no-cdn-fonts/'`n              }"
            }
        }
        
        if ($content -ne $originalContent) {
            $content | Set-Content $file.FullName -Encoding UTF8
            Write-Host "  ✓ 已修复" -ForegroundColor Green
            $fixedCount++
        } else {
            Write-Host "  ✗ 无法自动修复，请手动检查" -ForegroundColor Red
        }
    } elseif ($content -match "canvasKitBaseUrl") {
        Write-Host "  ✓ 已配置本地 CanvasKit" -ForegroundColor Green
        
        # 检查路径是否正确
        if ($file.FullName -match "backend\\static\\flutter-web" -and $content -match "canvasKitBaseUrl:\s*['/]*canvaskit" -and -not ($content -match "canvasKitBaseUrl:\s*'/static/flutter-web/canvaskit/'")) {
            Write-Host "  ⚠ 路径需要修正为 /static/flutter-web/canvaskit/" -ForegroundColor Yellow
            $content = $content -replace "canvasKitBaseUrl:\s*['/]*canvaskit[^'\"]*['\"]?", "canvasKitBaseUrl: '/static/flutter-web/canvaskit/'"
            $content | Set-Content $file.FullName -Encoding UTF8
            Write-Host "  ✓ 路径已修正" -ForegroundColor Green
            $fixedCount++
        }
    } else {
        Write-Host "  ? 未找到 CanvasKit 配置" -ForegroundColor Yellow
        
        # 尝试添加配置
        if ($content -match "initializeEngine\(\{") {
            Write-Host "  尝试添加 CanvasKit 配置..." -ForegroundColor Gray
            $content = $content -replace "(initializeEngine\(\{[^}]*?)\}", "`$1,`n                canvasKitBaseUrl: '/static/flutter-web/canvaskit/',`n                fontFallbackBaseUrl: '/no-cdn-fonts/'`n              }"
            
            if ($content -ne $originalContent) {
                $content | Set-Content $file.FullName -Encoding UTF8
                Write-Host "  ✓ 配置已添加" -ForegroundColor Green
                $fixedCount++
            }
        }
    }
}

Write-Host ""
Write-Host "修复完成: $fixedCount 个文件已修改" -ForegroundColor Green
Write-Host ""
Write-Host "重要提示:" -ForegroundColor Yellow
Write-Host "  1. 重新打包部署" -ForegroundColor Cyan
Write-Host "  2. 清除浏览器缓存后测试" -ForegroundColor Cyan
Write-Host "  3. 如果仍有问题，检查浏览器控制台的网络请求" -ForegroundColor Cyan
