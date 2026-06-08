# Build Owlangs Portable Executable
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
Write-Host "Building Owlangs Portable Edition" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Features:" -ForegroundColor Yellow
Write-Host "  - Single .exe file (double-click to run)" -ForegroundColor Gray
Write-Host "  - Auto-initializes user configs" -ForegroundColor Gray
Write-Host "  - Auto-starts server and opens browser" -ForegroundColor Gray
Write-Host "  - Configs persisted in C:\ProgramData\Owlangs" -ForegroundColor Gray
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
Write-Host "[build] Using launcher_portable.spec" -ForegroundColor Yellow

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
    pyinstaller -y --clean launcher_portable.spec
    
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[build] ERROR: PyInstaller build failed!" -ForegroundColor Red
        exit 1
    }
    
    Write-Host "[build] Portable executable built successfully!" -ForegroundColor Green
} finally {
    Remove-Item Env:\OWLANGS_VERSION -ErrorAction SilentlyContinue
    Remove-Item Env:\OWLANGS_FRONTEND -ErrorAction SilentlyContinue
    Remove-Item Env:\OWLANGS_INCLUDE_ANONYMIZE -ErrorAction SilentlyContinue
    Remove-Item Env:\OWLANGS_SKIP_SPACY -ErrorAction SilentlyContinue
}

Write-Host ""

# Stage 3rdParty files alongside the EXE (portable mode)
Write-Host "[staging] Staging 3rdParty files..." -ForegroundColor Cyan
$distDir = "dist"

# Clean old 3rdParty in dist to prevent Copy-Item nesting on re-runs
if (Test-Path "$distDir\3rdParty") {
    Remove-Item -Path "$distDir\3rdParty" -Recurse -Force
    Write-Host "[staging] Cleaned old dist/3rdParty" -ForegroundColor Yellow
}

# Copy Redis
if (Test-Path "3rdParty\windows\Redis-x64-3.0.504") {
    $dest = Join-Path $distDir "3rdParty\windows\Redis-x64-3.0.504"
    Write-Host "[staging] Copying Redis..." -ForegroundColor Yellow
    New-Item -ItemType Directory -Path $dest -Force | Out-Null
    Copy-Item -Path "3rdParty\windows\Redis-x64-3.0.504\*" -Destination $dest -Recurse -Force
}

# Copy Pandoc if available
if (Test-Path "3rdParty\windows") {
    $pandocDirs = Get-ChildItem -Path "3rdParty\windows" -Directory -Filter "pandoc-*" -ErrorAction SilentlyContinue
    foreach ($d in $pandocDirs) {
        $dest = Join-Path $distDir "3rdParty\windows\$($d.Name)"
        Write-Host "[staging] Copying $($d.Name)..." -ForegroundColor Yellow
        Copy-Item -Path $d.FullName -Destination $dest -Recurse -Force
    }
}

# Copy pdflatex if available
if (Test-Path "3rdParty\windows\pdflatex") {
    $dest = Join-Path $distDir "3rdParty\windows\pdflatex"
    Write-Host "[staging] Copying pdflatex..." -ForegroundColor Yellow
    Copy-Item -Path "3rdParty\windows\pdflatex" -Destination $dest -Recurse -Force
}

Write-Host "[staging] 3rdParty files staged" -ForegroundColor Green

Write-Host ""

# Create output directory
$packageName = "Owlangs-win64-portable-$Version"
$buildDir = "build\win\$packageName"

Write-Host "[package] Creating package: $packageName" -ForegroundColor Cyan

if (Test-Path $buildDir) {
    Remove-Item -Path $buildDir -Recurse -Force
}
New-Item -ItemType Directory -Path $buildDir -Force | Out-Null

# Copy the single-file executable
$exeName = "Owlangs-$Version.exe"
Copy-Item -Path "dist\$exeName" -Destination $buildDir -Force
Write-Host "[package] Executable: $exeName" -ForegroundColor Green

# Copy 3rdParty alongside the EXE in the package directory
if (Test-Path "dist\3rdParty") {
    Write-Host "[package] Copying 3rdParty to package..." -ForegroundColor Yellow
    Copy-Item -Path "dist\3rdParty" -Destination $buildDir -Recurse -Force
    Write-Host "[package] 3rdParty files packaged" -ForegroundColor Green
}

# Create README
$readmeContent = @"
Owlangs Portable Edition v$Version
===================================

Quick Start
-----------
Double-click `Owlangs-$Version.exe` to automatically:
1. Initialize config files (first run only)
2. Start the backend service
3. Open http://localhost:8800 in your browser

Config File Location
--------------------
C:\ProgramData\Owlangs\configs\
  - secrets.json    : API keys (required on first run)
  - system.json     : System settings
  - platforms.json  : Translation platform settings

Command-Line Options
--------------------
Owlangs-$Version.exe [options]

  (no arguments)      Start server and open browser (double-click friendly)
  --init-config       Initialize config files and exit
  --edit-config NAME  Edit a config file (e.g. `--edit-config secrets`)
  --port PORT         Specify port (default: 8800)
  --silent            Silent mode (no console output)

CLI Translation Commands
------------------------
Owlangs-$Version.exe <subcommand> [options]

  translate <file> --to <lang>       Translate one file
  convert <file>                     Convert document format (no translation)
  batch <ZIP> --to <lang>            Batch translate files in a ZIP
  platform list                      List available LLM platforms
  formats                            List supported file formats
  glossary list                      List glossaries
  config show                        Show config file path
  status <task_id>                   Query task status
  download <task_id> --type <fmt>    Download task result

Examples:
  Owlangs-$Version.exe translate report.pdf --to Chinese
  Owlangs-$Version.exe platform list --json
  Owlangs-$Version.exe config init

Notes
-----
- Configure API keys before first use
- Close the window to stop the service
- Config files are stored in C:\ProgramData\Owlangs and persist across reinstalls

Support
-------
If you run into issues, check logs at:
C:\ProgramData\Owlangs\logs\
"@

$readmePath = Join-Path $buildDir "README.txt"
$readmeContent | Set-Content -Path $readmePath -Encoding UTF8

Write-Host "[package] Package created at: $buildDir" -ForegroundColor Green

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "Portable Build Complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "输出文件:" -ForegroundColor Yellow
Write-Host "  $buildDir\$exeName" -ForegroundColor Cyan
Write-Host ""
Write-Host "使用方法:" -ForegroundColor Yellow
Write-Host "  1. 复制 Owlangs.exe 到任意位置" -ForegroundColor Gray
Write-Host "  2. 双击运行" -ForegroundColor Gray
Write-Host "  3. 首次运行配置 API 密钥" -ForegroundColor Gray
Write-Host ""
