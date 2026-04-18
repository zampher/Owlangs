# Build Owlangs Single-File Executable
# Creates a standalone .exe that auto-starts server and opens browser

param(
    [switch]$SkipFlutter,
    [switch]$NoSpacy,
    [switch]$IncludeAnonymize,
    [switch]$IncludePandoc
)

$ErrorActionPreference = "Stop"

# Import common build functions
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$CommonModule = Join-Path $ScriptDir "build_common.ps1"
if (Test-Path $CommonModule) {
    . $CommonModule
} else {
    Write-Host "ERROR: build_common.ps1 not found!" -ForegroundColor Red
    exit 1
}

# Get project root
$RootDir = Split-Path -Parent (Split-Path -Parent $ScriptDir)
Set-Location $RootDir

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Building Owlangs Single-File Edition" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Features:" -ForegroundColor Yellow
Write-Host "  - Single .exe file (double-click to run)" -ForegroundColor Gray
Write-Host "  - Auto-initializes user configs" -ForegroundColor Gray
Write-Host "  - Auto-starts server and opens browser" -ForegroundColor Gray
Write-Host "  - Configs persisted in C:\Users\Public\Owlangs" -ForegroundColor Gray
Write-Host ""

# Sync version
Write-Host "[setup] Syncing version numbers..." -ForegroundColor Cyan
$syncScript = Join-Path $RootDir "tools\setup\sync_version.ps1"
if (Test-Path $syncScript) {
    & $syncScript
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[setup] WARNING: Version sync failed, continuing..." -ForegroundColor Yellow
    }
} else {
    Write-Host "[setup] WARNING: sync_version.ps1 not found, skipping" -ForegroundColor Yellow
}
Write-Host ""

# Ensure virtual environment
Write-Host "[env] Setting up build environment..." -ForegroundColor Cyan
Ensure-BuildVenv

# Get version
$Version = Get-BuildVersion
Write-Host "[build] Version: $Version" -ForegroundColor Cyan
Write-Host ""

# Build Flutter Web frontend
if (-not $SkipFlutter) {
    Write-Host "[build] Building Flutter Web frontend..." -ForegroundColor Cyan
    $flutterResult = Build-FlutterWebUnified -CanvasKitPath "/static/flutter-web/canvaskit/"
    if (-not $flutterResult) {
        Write-Host "[build] ERROR: Flutter Web build failed!" -ForegroundColor Red
        exit 1
    }
    Write-Host ""
    
    # Verify CanvasKit configuration
    $indexHtmlPath = Join-Path $RootDir "backend\static\flutter-web\index.html"
    Test-CanvasKitConfig -IndexHtmlPath $indexHtmlPath
    Write-Host ""
} else {
    Write-Host "[build] Skipping Flutter Web build (--SkipFlutter)" -ForegroundColor Yellow
    Write-Host ""
}

# Install project dependencies
Write-Host "[env] Installing project dependencies..." -ForegroundColor Cyan
python -m pip install -e . | Out-Null
Write-Host ""

# Build single-file executable
Write-Host "[build] Building single-file executable..." -ForegroundColor Cyan
Write-Host "[build] Using launcher_singlefile.spec" -ForegroundColor Yellow

$env:OWLANGS_VERSION = $Version
$env:OWLANGS_FRONTEND = "web"

if ($IncludeAnonymize) {
    $env:OWLANGS_INCLUDE_ANONYMIZE = "1"
    Write-Host "[build] Including Anonymize feature" -ForegroundColor Cyan
}

if ($NoSpacy) {
    $env:OWLANGS_SKIP_SPACY = "1"
    Write-Host "[build] Skipping spaCy models" -ForegroundColor Cyan
}

if ($IncludePandoc) {
    Write-Host "[build] Including Pandoc support" -ForegroundColor Cyan
}

try {
    pyinstaller -y --clean launcher_singlefile.spec
    
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[build] ERROR: PyInstaller build failed!" -ForegroundColor Red
        exit 1
    }
    
    Write-Host "[build] Single-file executable built successfully!" -ForegroundColor Green
} finally {
    Remove-Item Env:\OWLANGS_VERSION -ErrorAction SilentlyContinue
    Remove-Item Env:\OWLANGS_FRONTEND -ErrorAction SilentlyContinue
    Remove-Item Env:\OWLANGS_INCLUDE_ANONYMIZE -ErrorAction SilentlyContinue
    Remove-Item Env:\OWLANGS_SKIP_SPACY -ErrorAction SilentlyContinue
}

Write-Host ""

# Stage 3rdParty files if needed
if ($IncludePandoc) {
    Write-Host "[staging] Including Pandoc and pdflatex..." -ForegroundColor Cyan
    $distDir = "dist\Owlangs"
    
    if (Test-Path "3rdParty\windows") {
        $pandocDirs = Get-ChildItem -Path "3rdParty\windows" -Directory -Filter "pandoc-*" -ErrorAction SilentlyContinue
        foreach ($d in $pandocDirs) {
            $dest = Join-Path $distDir "3rdParty\windows\$($d.Name)"
            Write-Host "[staging] Copying $($d.Name)..." -ForegroundColor Yellow
            Copy-Item -Path $d.FullName -Destination $dest -Recurse -Force
        }
        
        if (Test-Path "3rdParty\windows\pdflatex") {
            $dest = Join-Path $distDir "3rdParty\windows\pdflatex"
            Write-Host "[staging] Copying pdflatex..." -ForegroundColor Yellow
            Copy-Item -Path "3rdParty\windows\pdflatex" -Destination $dest -Recurse -Force
        }
        
        Write-Host "[staging] 3rdParty files staged" -ForegroundColor Green
    }
}

Write-Host ""

# Create output directory
$packageName = "Owlangs-SingleFile-$Version"
$buildDir = "build\win\$packageName"

Write-Host "[package] Creating package: $packageName" -ForegroundColor Cyan

if (Test-Path $buildDir) {
    Remove-Item -Path $buildDir -Recurse -Force
}
New-Item -ItemType Directory -Path $buildDir -Force | Out-Null

# Copy the single-file executable
Copy-Item -Path "dist\Owlangs.exe" -Destination $buildDir -Force
Write-Host "[package] Executable: Owlangs.exe" -ForegroundColor Green

# Create README
$readmeContent = @"
Owlangs Single-File Edition v$Version
=====================================

快速开始
--------
双击运行 Owlangs.exe，自动完成以下操作：
1. 初始化配置文件（首次运行）
2. 启动后端服务
3. 打开浏览器访问 http://localhost:8800

配置文件位置
------------
C:\Users\Public\Owlangs\configs\
  - secrets.json    : API 密钥（首次运行需要配置）
  - system.json     : 系统设置
  - platforms.json  : 翻译平台配置
  - ui.json         : 界面配置

命令行选项
----------
Owlangs.exe [选项]

  --init-config       初始化配置文件并退出
  --edit-config NAME  编辑配置文件（如: --edit-config secrets）
  --port PORT         指定端口（默认: 8800）
  --silent            静默模式（无控制台输出）

注意事项
--------
- 首次运行需要配置 API 密钥，程序会自动提示
- 关闭窗口即可停止服务
- 配置文件保存在 C:\Users\Public\Owlangs，重装系统不会丢失

技术支持
--------
如有问题，请查看日志文件：
C:\Users\Public\Owlangs\logs\
"@

$readmePath = Join-Path $buildDir "README.txt"
$readmeContent | Set-Content -Path $readmePath -Encoding UTF8

Write-Host "[package] Package created at: $buildDir" -ForegroundColor Green

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "Single-File Build Complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "输出文件:" -ForegroundColor Yellow
Write-Host "  $buildDir\Owlangs.exe" -ForegroundColor Cyan
Write-Host ""
Write-Host "使用方法:" -ForegroundColor Yellow
Write-Host "  1. 复制 Owlangs.exe 到任意位置" -ForegroundColor Gray
Write-Host "  2. 双击运行" -ForegroundColor Gray
Write-Host "  3. 首次运行配置 API 密钥" -ForegroundColor Gray
Write-Host ""
