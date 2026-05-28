# Build Owlangs Portable Edition (Onedir)
# Creates a folder-based portable build with fast CLI startup
# No onefile extraction overhead — files stay in a folder

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
Write-Host "Building Owlangs Portable Edition (Onedir)" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Features:" -ForegroundColor Yellow
Write-Host "  - Folder-based (no extraction overhead)" -ForegroundColor Gray
Write-Host "  - Fast CLI startup (~2s vs ~50s onefile)" -ForegroundColor Gray
Write-Host "  - Auto-initializes user configs" -ForegroundColor Gray
Write-Host "  - Auto-starts server and opens browser (double-click)" -ForegroundColor Gray
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

# Build onedir executable
Write-Host "[build] Building onedir portable executable..." -ForegroundColor Cyan
Write-Host "[build] Using launcher_portable_onedir.spec" -ForegroundColor Yellow

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
    pyinstaller -y --clean launcher_portable_onedir.spec

    if ($LASTEXITCODE -ne 0) {
        Write-Host "[build] ERROR: PyInstaller build failed!" -ForegroundColor Red
        exit 1
    }

    Write-Host "[build] Onedir portable build successful!" -ForegroundColor Green
} finally {
    Remove-Item Env:\OWLANGS_VERSION -ErrorAction SilentlyContinue
    Remove-Item Env:\OWLANGS_FRONTEND -ErrorAction SilentlyContinue
    Remove-Item Env:\OWLANGS_INCLUDE_ANONYMIZE -ErrorAction SilentlyContinue
    Remove-Item Env:\OWLANGS_SKIP_SPACY -ErrorAction SilentlyContinue
}

Write-Host ""

# Verify output
$distDirName = "Owlangs-$Version"
$distDir = Join-Path "dist" $distDirName
if (-not (Test-Path $distDir)) {
    Write-Host "[build] ERROR: Expected output directory not found: $distDir" -ForegroundColor Red
    exit 1
}

# Create output directory
$packageName = "Owlangs-win64-portable-$Version"
$buildDir = "build\win\$packageName"

Write-Host "[package] Creating package: $packageName" -ForegroundColor Cyan

if (Test-Path $buildDir) {
    Remove-Item -Path $buildDir -Recurse -Force
}
New-Item -ItemType Directory -Path $buildDir -Force | Out-Null

# Copy the entire onedir folder to package
Write-Host "[package] Copying onedir folder..." -ForegroundColor Yellow
Copy-Item -Path $distDir\* -Destination $buildDir -Recurse -Force
Write-Host "[package] Onedir folder copied" -ForegroundColor Green

# Stage 3rdParty files alongside the EXE (for easy user upgrades + path resolution)
Write-Host "[staging] Staging 3rdParty files to package root..." -ForegroundColor Cyan
$src3rdParty = Join-Path $RootDir "3rdParty"
if (Test-Path $src3rdParty) {
    $dst3rdParty = Join-Path $buildDir "3rdParty"
    if (Test-Path $dst3rdParty) {
        Remove-Item -Path $dst3rdParty -Recurse -Force
    }
    Copy-Item -Path $src3rdParty -Destination $dst3rdParty -Recurse -Force
    Write-Host "[staging] 3rdParty copied to package root" -ForegroundColor Green
} else {
    Write-Host "[staging] WARNING: 3rdParty source not found" -ForegroundColor Yellow
}

# Create README
$readmeContent = @"
Owlangs Portable Edition (Onedir) v$Version
==========================================

Quick Start
-----------
Double-click Owlangs-$Version.exe to automatically:
1. Initialize config files (first run only)
2. Start the backend service
3. Open http://localhost:8800 in your browser

For fast CLI usage, run from terminal:
  Owlangs-$Version.exe translate report.pdf --to Chinese
  Owlangs-$Version.exe platform list --json
  Owlangs-$Version.exe formats

Config File Location
--------------------
C:\ProgramData\Owlangs\configs\
  - secrets.json    : API keys (required on first run)
  - system.json     : System settings
  - platforms.json  : Translation platform settings
  - ui.json         : UI settings

Command-Line Options
--------------------
Owlangs-$Version.exe [options]

  (no arguments)      Start server and open browser (double-click friendly)
  --init-config       Initialize config files and exit
  --edit-config NAME  Edit a config file (e.g. --edit-config secrets)
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
- This is a folder-based (onedir) build — keep all files together
- Do not move Owlangs-$Version.exe out of this folder
- Configure API keys before first use
- Close the window to stop the service
- Config files persist across reinstalls

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
Write-Host "Portable Onedir Build Complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Output:" -ForegroundColor Yellow
Write-Host "  $buildDir\Owlangs-$Version.exe" -ForegroundColor Cyan
Write-Host ""
Write-Host "Distribution:" -ForegroundColor Yellow
Write-Host "  Zip the entire folder: $buildDir" -ForegroundColor Gray
Write-Host ""
Write-Host "Usage:" -ForegroundColor Yellow
Write-Host "  1. Copy the $packageName folder to any location" -ForegroundColor Gray
Write-Host "  2. Double-click Owlangs-$Version.exe to run server" -ForegroundColor Gray
Write-Host "  3. Or use CLI from terminal in that folder" -ForegroundColor Gray
Write-Host ""
