# Build Owlangs Portable Edition (Onedir + Launcher + Desktop)
# Creates a folder-based portable build with:
#   - Launcher (C# .NET 8) — entry point, manages backend & frontend
#   - Backend (PyInstaller onedir)
#   - Flutter Windows desktop frontend
#   - Flutter Web frontend (bundled inside backend _internal/)
#   - 3rdParty tools (Redis, etc.)
#
# Usage:
#   .\tools\build_win_portable_onedir.ps1             # full build
#   .\tools\build_win_portable_onedir.ps1 --SkipFlutter # skip web + desktop frontend
#   .\tools\build_win_portable_onedir.ps1 --SkipDesktop # skip desktop frontend & launcher

param(
    [switch]$SkipFlutter,
    [switch]$SkipDesktop,
    [switch]$NoSpacy,
    [switch]$IncludeAnonymize,
    [switch]$IncludePandoc
)

# ── Helper functions (defined before main body) ──

function Build-FlutterWindows {
    Write-Host "[frontend] Building Flutter Windows..." -ForegroundColor Cyan

    $frontendDir = "frontend"
    if (-not (Test-Path $frontendDir)) {
        Write-Host "[frontend] ERROR: frontend directory not found!" -ForegroundColor Red
        return $false
    }

    Push-Location $frontendDir

    try {
        Write-Host "[frontend] Running: flutter pub get" -ForegroundColor Yellow
        flutter pub get
        if ($LASTEXITCODE -ne 0) {
            Write-Host "[frontend] ERROR: flutter pub get failed!" -ForegroundColor Red
            return $false
        }

        Write-Host "[frontend] Running: flutter build windows --release" -ForegroundColor Yellow
        flutter build windows --release

        if ($LASTEXITCODE -ne 0) {
            Write-Host "[frontend] ERROR: Flutter Windows build failed!" -ForegroundColor Red
            return $false
        }

        # Copy all fonts to build output
        $buildFontsDir = "build\windows\x64\runner\Release\data\flutter_assets\fonts"
        if (-not (Test-Path $buildFontsDir)) {
            $buildFontsDir = "build\windows\runner\Release\data\flutter_assets\fonts"
        }
        if (-not (Test-Path $buildFontsDir)) {
            New-Item -ItemType Directory -Path $buildFontsDir -Force | Out-Null
        }

        $sourceFontsDir = "fonts"
        if (Test-Path $sourceFontsDir) {
            Write-Host "[frontend] Copying all fonts to Windows build output..." -ForegroundColor Yellow
            $fontFiles = Get-ChildItem -Path $sourceFontsDir -File
            $copiedCount = 0
            foreach ($fontFile in $fontFiles) {
                $destPath = Join-Path $buildFontsDir $fontFile.Name
                Copy-Item -Path $fontFile.FullName -Destination $destPath -Force
                $copiedCount++
            }
            Write-Host "[frontend] Fonts copied: $copiedCount files" -ForegroundColor Green
        }

        Write-Host "[frontend] Flutter Windows built successfully!" -ForegroundColor Green
        return $true
    } catch {
        Write-Host "[frontend] ERROR: Flutter Windows build error: $_" -ForegroundColor Red
        return $false
    } finally {
        Pop-Location
    }
}

function Build-Launcher {
    Write-Host "[launcher] Building Launcher..." -ForegroundColor Cyan

    $launcherDir = "launcher"
    if (-not (Test-Path $launcherDir)) {
        Write-Host "[launcher] WARNING: launcher directory not found, skipping Launcher build" -ForegroundColor Yellow
        return $false
    }

    # Check .NET SDK
    $dotnetVersion = dotnet --version 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[launcher] ERROR: .NET SDK not found. Please install .NET 8.0 SDK or later." -ForegroundColor Red
        return $false
    }
    Write-Host "[launcher] Found .NET SDK: $dotnetVersion" -ForegroundColor Green

    Push-Location $launcherDir

    try {
        Write-Host "[launcher] Running: dotnet build --configuration Release" -ForegroundColor Yellow
        $null = dotnet build --configuration Release 2>&1 | Tee-Object -Variable buildOutput

        $buildExitCode = $LASTEXITCODE
        $expectedOutputDir = "bin\Release\net8.0-windows\OwlangsLauncher.exe"
        $outputExists = Test-Path $expectedOutputDir

        if ($buildExitCode -ne 0 -or -not $outputExists) {
            Write-Host "[launcher] ERROR: Launcher build failed!" -ForegroundColor Red
            Write-Host "[launcher]   Exit code: $buildExitCode, Output exists: $outputExists" -ForegroundColor Red
            $buildOutput | Where-Object { $_ -match "error|Error|ERROR" } | Select-Object -First 10 | ForEach-Object {
                Write-Host "[launcher]   $_" -ForegroundColor Red
            }
            Pop-Location
            return $false
        }

        Write-Host "[launcher] Launcher built successfully!" -ForegroundColor Green
        return $true
    } catch {
        Write-Host "[launcher] ERROR: Launcher build exception: $_" -ForegroundColor Red
        Pop-Location
        return $false
    } finally {
        Pop-Location
    }
}

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
Write-Host "  - Launcher entry point (manages backend + frontend)" -ForegroundColor Gray
Write-Host "  - Flutter Windows desktop frontend" -ForegroundColor Gray
Write-Host "  - Flutter Web frontend (browser access)" -ForegroundColor Gray
Write-Host "  - Folder-based (no extraction overhead)" -ForegroundColor Gray
Write-Host "  - Auto-initializes user configs" -ForegroundColor Gray
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

# ── Step 1: Build Flutter Web frontend ──
if (-not $SkipFlutter) {
    Write-Host "[build] Building Flutter Web frontend..." -ForegroundColor Cyan
    $flutterWebResult = Build-FlutterWebUnified -CanvasKitPath "/static/flutter-web/canvaskit/"
    if (-not $flutterWebResult) {
        Write-Host "[build] ERROR: Flutter Web build failed!" -ForegroundColor Red
        exit 1
    }

    # Verify CanvasKit configuration
    $indexHtmlPath = Join-Path $RootDir "backend\static\flutter-web\index.html"
    Test-CanvasKitConfig -IndexHtmlPath $indexHtmlPath
    Write-Host ""
} else {
    Write-Host "[build] Skipping Flutter Web build (--SkipFlutter)" -ForegroundColor Yellow
    Write-Host ""
}

# ── Step 2: Build Flutter Windows desktop frontend ──
if (-not $SkipDesktop) {
    Write-Host "[build] Building Flutter Windows desktop frontend..." -ForegroundColor Cyan
    $flutterDesktopResult = Build-FlutterWindows
    if (-not $flutterDesktopResult) {
        Write-Host "[build] ERROR: Flutter Windows build failed!" -ForegroundColor Red
        exit 1
    }
    Write-Host ""
} else {
    Write-Host "[build] Skipping Flutter Windows desktop frontend (--SkipDesktop)" -ForegroundColor Yellow
    Write-Host ""
}

# Install project dependencies
Write-Host "[env] Installing project dependencies..." -ForegroundColor Cyan
python -m pip install -e . | Out-Null
Write-Host ""

# ── Step 3: Build backend with PyInstaller onedir ──
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

# ── Step 4: Build Launcher (C# .NET 8) ──
if (-not $SkipDesktop) {
    Write-Host "[launcher] Building Launcher..." -ForegroundColor Cyan
    # Sync launcher icon before building
    $syncIconScript = Join-Path $ScriptDir "sync_launcher_icon.ps1"
    & $syncIconScript -RootDir $RootDir | Out-Null

    $launcherBuildResult = Build-Launcher
    if ($launcherBuildResult -eq $false) {
        Write-Host "[launcher] ERROR: Launcher build failed!" -ForegroundColor Red
        exit 1
    }
    Write-Host ""
} else {
    Write-Host "[launcher] Skipping Launcher build (--SkipDesktop)" -ForegroundColor Yellow
    Write-Host ""
}

# ── Step 5: Create package directory ──
$packageName = "Owlangs-win64-portable-$Version"
$buildDir = "build\win\$packageName"

Write-Host "[package] Creating package: $packageName" -ForegroundColor Cyan

if (Test-Path $buildDir) {
    Remove-Item -Path $buildDir -Recurse -Force
}
New-Item -ItemType Directory -Path $buildDir -Force | Out-Null

# Copy the entire PyInstaller onedir folder into bin/
Write-Host "[package] Copying backend onedir to bin/..." -ForegroundColor Yellow
New-Item -ItemType Directory -Path "$buildDir\bin" -Force | Out-Null
Copy-Item -Path $distDir\* -Destination "$buildDir\bin" -Recurse -Force

# Move configs from bin/_internal/configs/ to bin/configs/ for easy user access,
# while keeping them available inside _internal/ for the backend runtime
$internalConfigs = Join-Path $buildDir "bin\_internal\configs"
if (Test-Path $internalConfigs) {
    Write-Host "[package] Configs found in _internal/, copying to bin/configs/..." -ForegroundColor Yellow
    $binConfigsDir = Join-Path $buildDir "bin\configs"
    New-Item -ItemType Directory -Path $binConfigsDir -Force | Out-Null
    Copy-Item -Path "$internalConfigs\*" -Destination $binConfigsDir -Recurse -Force
}

# ── Step 6: Copy Launcher into package ──
if (-not $SkipDesktop) {
    Write-Host "[package] Copying Launcher..." -ForegroundColor Yellow
    $launcherReleaseDir = "launcher\bin\Release\net8.0-windows"
    $launcherPackageDir = "$buildDir\launcher"

    if (Test-Path $launcherReleaseDir) {
        New-Item -ItemType Directory -Path $launcherPackageDir -Force | Out-Null

        # Copy Launcher files, excluding debug/symbol files
        $excludePatterns = @("*.pdb", "*.deps.json", "*.xml", "*.rsp", "*.pri")
        Get-ChildItem -Path $launcherReleaseDir -File | Where-Object {
            $shouldExclude = $false
            foreach ($pattern in $excludePatterns) {
                if ($_.Name -like $pattern) {
                    $shouldExclude = $true
                    break
                }
            }
            -not $shouldExclude
        } | ForEach-Object {
            Copy-Item -Path $_.FullName -Destination $launcherPackageDir -Force
        }

        # Copy Resources (icon.ico)
        $resourcesSource = Join-Path $launcherReleaseDir "Resources"
        if (Test-Path $resourcesSource) {
            $resourcesDest = Join-Path $launcherPackageDir "Resources"
            New-Item -ItemType Directory -Path $resourcesDest -Force | Out-Null
            Copy-Item -Path "$resourcesSource\*" -Destination $resourcesDest -Recurse -Force
        }

        # Copy runtimes (native .NET runtime files)
        $runtimesSource = Join-Path $launcherReleaseDir "runtimes"
        if (Test-Path $runtimesSource) {
            $runtimesDest = Join-Path $launcherPackageDir "runtimes"
            New-Item -ItemType Directory -Path $runtimesDest -Force | Out-Null
            Copy-Item -Path "$runtimesSource\*" -Destination $runtimesDest -Recurse -Force
        }

        Write-Host "[package] Launcher copied" -ForegroundColor Green
    } else {
        Write-Host "[package] ERROR: Launcher release directory not found: $launcherReleaseDir" -ForegroundColor Red
        exit 1
    }
}

# ── Step 7: Copy desktop frontend into package ──
if (-not $SkipDesktop) {
    Write-Host "[package] Copying Flutter Windows desktop frontend..." -ForegroundColor Yellow
    $flutterWindowsBuildDir = "frontend\build\windows\x64\runner\Release"
    $flutterWindowsPackageDir = "$buildDir\frontend"

    # Fallback to old path
    if (-not (Test-Path $flutterWindowsBuildDir)) {
        $flutterWindowsBuildDir = "frontend\build\windows\runner\Release"
    }

    if (Test-Path $flutterWindowsBuildDir) {
        New-Item -ItemType Directory -Path $flutterWindowsPackageDir -Force | Out-Null
        Copy-Item -Path "$flutterWindowsBuildDir\*" -Destination $flutterWindowsPackageDir -Recurse -Force
        Write-Host "[package] Desktop frontend copied" -ForegroundColor Green
    } else {
        Write-Host "[package] WARNING: Flutter Windows build directory not found, skipping" -ForegroundColor Yellow
    }
}

# ── Step 8: Stage 3rdParty files to package root ──
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

# Create launcher batch file at package root (convenient entry point)
$batPath = Join-Path $buildDir "Start_Owlangs.bat"
@"
@echo off
start "" "%~dp0launcher\OwlangsLauncher.exe"
"@ | Set-Content -Path $batPath -Encoding ASCII
Write-Host "[package] Created Owlangs.bat at package root" -ForegroundColor Green

# ── Step 9: Create README ──
if (-not $SkipDesktop) {
    $readmeContent = @"
Owlangs Portable Edition (Onedir) v$Version
==========================================

Quick Start
-----------
Double-click Start_Owlangs.bat at the package root, or directly run
launcher\OwlangsLauncher.exe to automatically:
1. Start the backend service
2. Launch the desktop app (frontend\owlangs.exe)
3. Also accessible via browser at http://localhost:8800

For CLI usage, open a terminal in this folder and run:
  bin\Owlangs-win.exe translate report.pdf --to Chinese
  bin\Owlangs-win.exe platform list --json

Config File Location
--------------------
C:\ProgramData\Owlangs\configs\
  - secrets.json    : API keys (required on first run)
  - system.json     : System settings
  - platforms.json  : Translation platform settings

Templates are available in: bin\configs\

Directory Layout
----------------
  launcher\           - OwlangsLauncher.exe (.NET 8) — entry point
  bin\                - Backend (Python) executable & runtime
  frontend\           - Flutter Windows desktop app
  3rdParty\           - Third-party tools (Redis, pandoc, etc.)

Notes
-----
- This is a folder-based (onedir) build — keep all files together
- Double-click OwlangsLauncher.exe to start (not the backend exe)
- The system tray icon appears after Launcher starts
- Configure API keys before first use (see C:\ProgramData\Owlangs\configs\)
- Config files persist across reinstalls

Support
-------
If you run into issues, check logs at:
C:\ProgramData\Owlangs\logs\
"@
} else {
    $readmeContent = @"
Owlangs Portable Edition (Onedir - CLI Only) v$Version
===============================================

Quick Start
-----------
Double-click bin\Owlangs-win.exe to automatically:
1. Initialize config files (first run only)
2. Start the backend service
3. Open http://localhost:8800 in your browser

For CLI usage, run from terminal:
  bin\Owlangs-win.exe translate report.pdf --to Chinese
  bin\Owlangs-win.exe platform list --json

Config File Location
--------------------
C:\ProgramData\Owlangs\configs\
  - secrets.json    : API keys (required on first run)
  - system.json     : System settings
  - platforms.json  : Translation platform settings

Templates are available in: bin\configs\

Notes
-----
- This is a folder-based (onedir) build — keep all files together
- Configure API keys before first use
- Config files persist across reinstalls

Support
-------
If you run into issues, check logs at:
C:\ProgramData\Owlangs\logs\
"@
}

$readmePath = Join-Path $buildDir "README.txt"
$readmeContent | Set-Content -Path $readmePath -Encoding UTF8

Write-Host "[package] Package created at: $buildDir" -ForegroundColor Green

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "Portable Onedir Build Complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Output:" -ForegroundColor Yellow
Write-Host "  $buildDir" -ForegroundColor Cyan
Write-Host ""
if (-not $SkipDesktop) {
    Write-Host "Entry point:" -ForegroundColor Yellow
    Write-Host "  $buildDir\Start_Owlangs.bat" -ForegroundColor Cyan
    Write-Host "  (or directly: $buildDir\launcher\OwlangsLauncher.exe)" -ForegroundColor Gray
    Write-Host ""
}
Write-Host "Distribution:" -ForegroundColor Yellow
Write-Host "  Zip the entire folder: $buildDir" -ForegroundColor Gray
Write-Host ""

Write-Host ""

