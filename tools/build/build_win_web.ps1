# Build Owlangs Web Version Windows installer package
# This version includes:
# - Backend EXE (PyInstaller) with Flutter Web frontend bundled
# - Redis service binaries
# - Configuration templates
# - spaCy models
# Usage:
#   tools/build_win_web.ps1            # build lite version
#   tools/build_win_web.ps1 --lite    # build lite version
#   tools/build_win_web.ps1 --full    # build full version
#   tools/build_win_web.ps1 --clean   # clean all build artifacts

param(
    [string]$param1 = ""
)

$ErrorActionPreference = "Stop"

# Get script directory and project root
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RootDir = Split-Path -Parent (Split-Path -Parent $ScriptDir)
Set-Location $RootDir

# Ensure virtual environment
function Ensure-Venv {
    if (-not (Test-Path ".venv")) {
        Write-Host "[env] Creating virtual environment..." -ForegroundColor Yellow
        python -m venv .venv
    }
    
    Write-Host "[env] Activating virtual environment..." -ForegroundColor Yellow
    & ".venv\Scripts\Activate.ps1"
    
    Write-Host "[env] Upgrading pip..." -ForegroundColor Yellow
    python -m pip install --upgrade pip | Out-Null
    
    # Install PyInstaller
    Write-Host "[env] Installing PyInstaller..." -ForegroundColor Yellow
    python -m pip install pyinstaller | Out-Null
}

# Note: This script is independent and includes all necessary functions

# Sync version before building
Write-Host "Syncing version numbers..." -ForegroundColor Cyan
$syncScript = Join-Path $RootDir "tools\setup\sync_version.ps1"
if (Test-Path $syncScript) {
    & $syncScript
    if ($LASTEXITCODE -ne 0) {
        Write-Host "WARNING: Version sync failed, continuing with build..." -ForegroundColor Yellow
    }
} else {
    Write-Host "WARNING: sync_version.ps1 not found, skipping version sync" -ForegroundColor Yellow
}
Write-Host ""

# Get version
function Get-Version {
    $oldErrorAction = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $version = python -c "import backend; print(backend.__version__)" 2>&1
        if ($LASTEXITCODE -eq 0 -and $version -and -not ($version -match "Error|Traceback")) {
            return $version.Trim()
        }
    } catch {
    } finally {
        $ErrorActionPreference = $oldErrorAction
    }
    
    try {
        $pyCmd = @"
import tomllib
from pathlib import Path
pyproject_path = Path("pyproject.toml")
data = tomllib.loads(pyproject_path.read_text("utf-8"))
version = data.get("project", {}).get("version", "0.0.0")
print(version)
"@
        $version = python -c $pyCmd 2>&1
        if ($LASTEXITCODE -eq 0 -and $version -and -not ($version -match "Error|Traceback")) {
            return $version.Trim()
        }
    } catch {
    }
    
    return "0.0.0"
}

# Build PyInstaller
function Build-PyInstaller {
    param($SpecFile, $Version)
    $env:OWLANGS_VERSION = $Version
    Write-Host "[build] pyinstaller -y $SpecFile (version: $Version)" -ForegroundColor Yellow
    pyinstaller -y --clean $SpecFile
    Remove-Item Env:\OWLANGS_VERSION -ErrorAction SilentlyContinue
}

# Build download_models.exe
function Build-DownloadModels {
    Write-Host "[build] Building download_models.exe..." -ForegroundColor Yellow
    
    # Check if download_models.spec exists
    if (-not (Test-Path "download_models.spec")) {
        Write-Host "[build] ERROR: download_models.spec not found!" -ForegroundColor Red
        return $false
    }
    
    # Build with PyInstaller
    pyinstaller -y --clean download_models.spec
    $buildSuccess = $LASTEXITCODE -eq 0
    
    if (-not $buildSuccess) {
        Write-Host "[build] ERROR: download_models.exe build failed!" -ForegroundColor Red
        return $false
    }
    
    # Check if executable was created
    $exePath = "dist\download_models.exe"
    if (-not (Test-Path $exePath)) {
        Write-Host "[build] ERROR: download_models.exe not found in dist!" -ForegroundColor Red
        return $false
    }
    
    Write-Host "[build] ✓ download_models.exe built successfully" -ForegroundColor Green
    return $true
}

# Build Flutter Web (copy from main script logic)
function Build-FlutterWeb {
    Write-Host "[frontend] Building Flutter Web..." -ForegroundColor Cyan
    
    $frontendDir = "frontend"
    if (-not (Test-Path $frontendDir)) {
        Write-Host "[frontend] WARNING: frontend directory not found, skipping Flutter Web build" -ForegroundColor Yellow
        return
    }
    
    Push-Location $frontendDir
    
    try {
        Write-Host "[frontend] Running: flutter clean" -ForegroundColor Yellow
        flutter clean
        if ($LASTEXITCODE -ne 0) {
            Write-Host "[frontend] ERROR: flutter clean failed!" -ForegroundColor Red
            throw "Flutter clean failed"
        }

        Write-Host "[frontend] Running: flutter pub get" -ForegroundColor Yellow
        flutter pub get
        if ($LASTEXITCODE -ne 0) {
            Write-Host "[frontend] ERROR: flutter pub get failed!" -ForegroundColor Red
            throw "Flutter pub get failed"
        }

        Write-Host "[frontend] Running: flutter build web --release --no-tree-shake-icons (HTML renderer)" -ForegroundColor Yellow
        $env:FLUTTER_WEB_RENDERER = "html"
        flutter build web --release --no-tree-shake-icons
        Remove-Item Env:\FLUTTER_WEB_RENDERER -ErrorAction SilentlyContinue
        
        if ($LASTEXITCODE -ne 0) {
            Write-Host "[frontend] ERROR: Flutter Web build failed!" -ForegroundColor Red
            throw "Flutter Web build failed"
        }
        
        # Copy all fonts to build output
        $buildFontsDir = "build\web\assets\fonts"
        if (-not (Test-Path $buildFontsDir)) {
            New-Item -ItemType Directory -Path $buildFontsDir -Force | Out-Null
        }
        
        $sourceFontsDir = "fonts"
        if (Test-Path $sourceFontsDir) {
            Write-Host "[frontend] Copying all fonts to build output..." -ForegroundColor Yellow
            $fontFiles = Get-ChildItem -Path $sourceFontsDir -File
            $copiedCount = 0
            foreach ($fontFile in $fontFiles) {
                $destPath = Join-Path $buildFontsDir $fontFile.Name
                Copy-Item -Path $fontFile.FullName -Destination $destPath -Force
                $copiedCount++
            }
            Write-Host "[frontend] Fonts copied: $copiedCount files" -ForegroundColor Green
        }
        
        # Copy to backend static directory
        $backendStaticDir = "..\backend\static\flutter-web"
        Write-Host "[frontend] Copying build output to $backendStaticDir..." -ForegroundColor Yellow
        New-Item -ItemType Directory -Path $backendStaticDir -Force | Out-Null
        
        # Explicitly copy canvaskit directory first (ensure it's included)
        $canvaskitSource = "build\web\canvaskit"
        $canvaskitDest = Join-Path $backendStaticDir "canvaskit"
        if (Test-Path $canvaskitSource) {
            Write-Host "[frontend] Copying CanvasKit files..." -ForegroundColor Yellow
            if (Test-Path $canvaskitDest) {
                Remove-Item -Recurse -Force $canvaskitDest
            }
            Copy-Item -Path $canvaskitSource -Destination $backendStaticDir -Recurse -Force
            $canvaskitFiles = (Get-ChildItem -Path $canvaskitDest -Recurse -File).Count
            Write-Host "[frontend] ✓ CanvasKit files copied: $canvaskitFiles files" -ForegroundColor Green
        } else {
            Write-Host "[frontend] ⚠ Warning: CanvasKit source not found at $canvaskitSource" -ForegroundColor Yellow
        }
        
        # Copy other build output files
        Get-ChildItem -Path "build\web" | Where-Object { $_.Name -ne "canvaskit" } | ForEach-Object {
            $destPath = Join-Path $backendStaticDir $_.Name
            if ($_.PSIsContainer) {
                if (Test-Path $destPath) { Remove-Item -Recurse -Force $destPath }
                Copy-Item -Path $_.FullName -Destination $destPath -Recurse -Force
            } else {
                Copy-Item -Path $_.FullName -Destination $destPath -Force
            }
        }
        
        # Fix base href and CanvasKit path for PyInstaller packaged version
        $indexHtmlPath = Join-Path $backendStaticDir "index.html"
        if (Test-Path $indexHtmlPath) {
            Write-Host "[frontend] Fixing base href and CanvasKit path in index.html..." -ForegroundColor Yellow
            $content = Get-Content -Path $indexHtmlPath -Raw
            # Replace various possible base href formats
            $content = $content -replace '<base href="/">', '<base href="/static/flutter-web/">'
            $content = $content -replace '<base href="\$FLUTTER_BASE_HREF">', '<base href="/static/flutter-web/">'
            $content = $content -replace '<base href="">', '<base href="/static/flutter-web/">'
            # Also handle single quotes just in case
            $content = $content -replace "<base href='/'>" , '<base href="/static/flutter-web/">'
            $content = $content -replace "<base href='\`$FLUTTER_BASE_HREF'>" , '<base href="/static/flutter-web/">'
            # Fix CanvasKit base URL to use local path
            $content = $content -replace "canvasKitBaseUrl:\s*'/canvaskit/'", "canvasKitBaseUrl: '/static/flutter-web/canvaskit/'"
            $content = $content -replace 'canvasKitBaseUrl:\s*"/canvaskit/"', "canvasKitBaseUrl: '/static/flutter-web/canvaskit/'"
            Set-Content -Path $indexHtmlPath -Value $content -NoNewline
            Write-Host "[frontend] Base href fixed to /static/flutter-web/" -ForegroundColor Green
            
            # Verify the fix
            $verifyContent = Get-Content -Path $indexHtmlPath -Raw
            if ($verifyContent -match '<base href="/static/flutter-web/">') {
                Write-Host "[frontend] ✓ Verified: base href is correct" -ForegroundColor Green
            } else {
                Write-Host "[frontend] ⚠ Warning: base href fix may not have applied correctly" -ForegroundColor Yellow
                Write-Host "[frontend]   Current base tag: $(($verifyContent | Select-String '<base[^>]*>' | Select-Object -First 1).Matches.Value)" -ForegroundColor Yellow
            }
            
            # Verify CanvasKit path
            if ($verifyContent -match "canvasKitBaseUrl:\s*'/static/flutter-web/canvaskit/'") {
                Write-Host "[frontend] ✓ Verified: CanvasKit path is correct" -ForegroundColor Green
            } else {
                Write-Host "[frontend] ⚠ Warning: CanvasKit path may not be correct" -ForegroundColor Yellow
            }
        }
        
        # Final verification of CanvasKit files
        if (Test-Path $canvaskitDest) {
            $canvaskitFiles = (Get-ChildItem -Path $canvaskitDest -Recurse -File).Count
            Write-Host "[frontend] ✓ CanvasKit files ready: $canvaskitFiles files (offline ready)" -ForegroundColor Green
        } else {
            Write-Host "[frontend] ✗ Error: CanvasKit not found in destination" -ForegroundColor Red
        }
        
        Write-Host "[frontend] Flutter Web built and copied successfully!" -ForegroundColor Green
    } finally {
        Pop-Location
    }
}

# Create Web version package (no Windows desktop components)
function Make-WinPackage-Web {
    param($Version, $IsFull = $false)
    
    $packageType = if ($IsFull) { "full-web" } else { "lite-web" }
    $packageNameSuffix = if ($IsFull) { "-full-web" } else { "-web" }
    $packageDisplaySuffix = if ($IsFull) { " full (Web)" } else { " (Web)" }
    $packageDisplayName = "Owlangs$packageDisplaySuffix"
    $outDir = "build\win"
    $outDirFull = Join-Path $RootDir $outDir
    if (-not (Test-Path $outDirFull)) {
        New-Item -ItemType Directory -Path $outDirFull -Force | Out-Null
    }
    $packageDirName = "Owlangs$packageNameSuffix-$Version"
    $packageRoot = Join-Path $outDirFull $packageDirName
    $exeName = "Owlangs-win.exe"   # Fixed name (no version) for simpler version updates
    $appBin = "dist\$exeName"
    
    if (-not (Test-Path $appBin)) {
        Write-Host "[$packageType] Binary not found: $appBin" -ForegroundColor Red
        return $false
    }
    
    # Clean and create package structure
    if (Test-Path $packageRoot) {
        Remove-Item -Recurse -Force $packageRoot
    }
    New-Item -ItemType Directory -Path $packageRoot -Force | Out-Null
    New-Item -ItemType Directory -Path "$packageRoot\bin" -Force | Out-Null
    New-Item -ItemType Directory -Path "$packageRoot\config" -Force | Out-Null
    New-Item -ItemType Directory -Path "$packageRoot\config\templates" -Force | Out-Null
    
    # Copy executable
    Copy-Item $appBin "$packageRoot\bin\"
    
    # Copy download_models.exe if it exists
    $downloadModelsExe = "dist\download_models.exe"
    if (Test-Path $downloadModelsExe) {
        Write-Host "[$packageType] Copying download_models.exe..." -ForegroundColor Yellow
        Copy-Item $downloadModelsExe "$packageRoot\bin\"
        Write-Host "[$packageType] Copied download_models.exe" -ForegroundColor Green
    } else {
        Write-Host "[$packageType] WARNING: download_models.exe not found, skipping..." -ForegroundColor Yellow
    }
    
    # spaCy models are NOT copied to installation directory
    # Models should be downloaded to C:\ProgramData\Owlangs\models\spacy at runtime
    # This avoids permission issues and allows models to be shared across users
    Write-Host "[$packageType] Skipping spaCy models (will be downloaded to C:\ProgramData\Owlangs\models\spacy at runtime)" -ForegroundColor Gray
    
    # Copy Redis binaries (exclude .pdb, .docx, and other non-runtime files)
    $redisSourceDir = "3rdParty\windows\Redis-x64-3.0.504"
    $redisPackageDir = "$packageRoot\3rdParty\windows\Redis-x64-3.0.504"
    $redisExcludeExtensions = @('.pdb', '.docx', '.doc', '.md', '.txt', '.html', '.rtf')
    if (Test-Path $redisSourceDir) {
        Write-Host "[$packageType] Copying Redis binaries (excluding .pdb, .docx, docs)..." -ForegroundColor Yellow
        New-Item -ItemType Directory -Path $redisPackageDir -Force | Out-Null
        Get-ChildItem -Path $redisSourceDir -File | Where-Object {
            $ext = $_.Extension.ToLowerInvariant()
            $redisExcludeExtensions -notcontains $ext
        } | ForEach-Object {
            Copy-Item -Path $_.FullName -Destination $redisPackageDir -Force
        }
        Write-Host "[$packageType] Copied Redis" -ForegroundColor Green
    }
    
    # Copy ONLY template files (*.template) and public assets into package.
    # Runtime configs (secrets.json, local_users.json, local.json, etc.) are
    # initialized from templates on first run — bundling dev copies leaks
    # API keys, password hashes, and other sensitive data.
    $configSourceDir = Join-Path $RootDir "configs"
    if (Test-Path $configSourceDir) {
        Write-Host "[$packageType] Copying config templates (excluding runtime configs)..." -ForegroundColor Yellow
        Get-ChildItem -Path $configSourceDir -File | Where-Object {
            $_.Extension -eq '.template' -or $_.Name -eq 'donor_license_public.pem'
        } | ForEach-Object {
            Copy-Item -Path $_.FullName -Destination "$packageRoot\config\" -Force
        }
        Write-Host "[$packageType] Copied config templates only (dev runtime configs excluded)" -ForegroundColor Green
    }
    
    # Create batch launcher (starts backend directly for Web version)
    $launcherName = if ($IsFull) { "Owlangs-full-web.bat" } else { "Owlangs-web.bat" }
    $launcherContent = @"
@echo off
setlocal
cd /d "%~dp0bin"
if not exist "$exeName" (
    echo ERROR: Backend executable not found: $exeName
    pause
    exit /b 1
)
echo Starting $packageDisplayName...
echo The web interface will be available at: http://localhost:8800
start "" "$exeName"
"@
    $launcherContent | Out-File -FilePath "$packageRoot\$launcherName" -Encoding ASCII
    
    Write-Host "[$packageType] Package created: $packageRoot" -ForegroundColor Green
    return $true
}

# Main execution
Write-Host "Building Owlangs Web Version Windows package..." -ForegroundColor Green

if ($param1 -eq "--clean") {
    # Clean build artifacts
    Write-Host "Cleaning build artifacts..." -ForegroundColor Yellow
    $dirs = @("frontend\build\web", "dist", "build", "build\win")
    foreach ($dir in $dirs) {
        if (Test-Path $dir) {
            Remove-Item -Path $dir -Recurse -Force -ErrorAction SilentlyContinue
            Write-Host "  Removed: $dir" -ForegroundColor Gray
        }
    }
    exit 0
}

# Ensure virtual environment is activated
Ensure-Venv

# Determine what to build
$want_lite = $true
$want_full = $false
if ($param1 -eq "--full") {
    $want_lite = $false
    $want_full = $true
    Write-Host "Building FULL Web version only" -ForegroundColor Cyan
} else {
    Write-Host "Building LITE Web version only" -ForegroundColor Cyan
}

# Build download_models.exe
Write-Host "`n[build] Building download_models.exe..." -ForegroundColor Cyan
if (-not (Build-DownloadModels)) {
    Write-Host "`n❌ BUILD FAILED: download_models.exe build failed!" -ForegroundColor Red
    Write-Host "   Please fix the errors above and try again." -ForegroundColor Yellow
    exit 1
}

# Build Flutter Web frontend
Build-FlutterWeb

# Build backend with PyInstaller
if ($want_lite) {
    $version = Get-Version
    Build-PyInstaller -SpecFile "lite.spec" -Version $version
    if (Make-WinPackage-Web -Version $version -IsFull $false) {
        Write-Host "LITE Web package created successfully!" -ForegroundColor Green
    }
}

if ($want_full) {
    $version = Get-Version
    Build-PyInstaller -SpecFile "full.spec" -Version $version
    if (Make-WinPackage-Web -Version $version -IsFull $true) {
        Write-Host "FULL Web package created successfully!" -ForegroundColor Green
    }
}

Write-Host "`nBuild completed!" -ForegroundColor Green
Write-Host "Web version packages are in: build\win\" -ForegroundColor Cyan
