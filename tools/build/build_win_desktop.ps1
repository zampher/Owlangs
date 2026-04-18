# Build Owlangs Windows Desktop Version installer package
# This version includes:
# - Backend EXE (PyInstaller)
# - Flutter Windows desktop frontend
# - Launcher EXE (C# .NET 8) - manages backend and frontend
# - Configuration templates
# - spaCy models
# Note: Redis is NOT included - desktop version uses in-memory session storage (REDIS_ENABLED=false)
# Usage:
#   tools/build_win_desktop.ps1            # build lite version
#   tools/build_win_desktop.ps1 --lite    # build lite version
#   tools/build_win_desktop.ps1 --full    # build full version
#   tools/build_win_desktop.ps1 --clean   # clean all build artifacts

param(
    [string]$param1 = ""
)

# Set console output encoding to UTF-8 to prevent Chinese character corruption
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8
chcp 65001 | Out-Null

$ErrorActionPreference = "Stop"

# Get script directory and project root
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RootDir = Split-Path -Parent (Split-Path -Parent $ScriptDir)
Set-Location $RootDir

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
    $buildSuccess = $LASTEXITCODE -eq 0
    Remove-Item Env:\OWLANGS_VERSION -ErrorAction SilentlyContinue
    
    if (-not $buildSuccess) {
        Write-Host "[build] ERROR: PyInstaller build failed!" -ForegroundColor Red
        return $false
    }
    
    return $true
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

# Build Flutter Windows (copy from main script logic)
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
        # Flutter Windows builds to x64\runner\Release (architecture-specific path)
        $buildFontsDir = "build\windows\x64\runner\Release\data\flutter_assets\fonts"
        if (-not (Test-Path $buildFontsDir)) {
            # Fallback to old path structure
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
        Write-Host "[frontend] Build output: frontend\build\windows\runner\Release" -ForegroundColor Cyan
        return $true
    } catch {
        Write-Host "[frontend] ERROR: Flutter Windows build error: $_" -ForegroundColor Red
        return $false
    } finally {
        Pop-Location
    }
}

# Build Launcher (C# .NET 8)
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
    
    # Sync launcher icon from canonical Flutter ICO (see tools/generate_ico.py --frontend)
    $syncIconScript = Join-Path $ScriptDir "sync_launcher_icon.ps1"
    & $syncIconScript -RootDir $RootDir | Out-Null
    
    Push-Location $launcherDir
    
    $buildSuccess = $false
    try {
        Write-Host "[launcher] Running: dotnet build --configuration Release" -ForegroundColor Yellow
        $null = dotnet build --configuration Release 2>&1 | Tee-Object -Variable buildOutput
        
        # Check exit code immediately after command
        $buildExitCode = $LASTEXITCODE
        
        # Also verify the output directory exists
        $expectedOutputDir = "bin\Release\net8.0-windows\OwlangsLauncher.exe"
        $outputExists = Test-Path $expectedOutputDir
        
        if ($buildExitCode -ne 0 -or -not $outputExists) {
            Write-Host "[launcher] ERROR: Launcher build failed!" -ForegroundColor Red
            Write-Host "[launcher]   Exit code: $buildExitCode" -ForegroundColor Red
            Write-Host "[launcher]   Output exists: $outputExists" -ForegroundColor Red
            if (-not $outputExists) {
                Write-Host "[launcher]   Expected output: $expectedOutputDir" -ForegroundColor Yellow
            }
            # Show build errors if any
            $buildOutput | Where-Object { $_ -match "error|Error|ERROR" } | Select-Object -First 10 | ForEach-Object {
                # Ensure proper encoding for error output
                $errorLine = [Console]::OutputEncoding.GetString([Console]::OutputEncoding.GetBytes($_))
                Write-Host "[launcher]   $errorLine" -ForegroundColor Red
            }
            Pop-Location
            return $false
        }
        
        Write-Host "[launcher] Launcher built successfully!" -ForegroundColor Green
        $buildSuccess = $true
    } catch {
        Write-Host "[launcher] ERROR: Launcher build exception: $_" -ForegroundColor Red
        $buildSuccess = $false
    } finally {
        Pop-Location
    }
    
    return $buildSuccess
}

# Create Desktop version package (includes Windows frontend and Launcher)
function Make-WinPackage-Desktop {
    param($Version, $IsFull = $false)
    
    $packageType = if ($IsFull) { "full-desktop" } else { "lite-desktop" }
    $packageNameSuffix = if ($IsFull) { "-full-desktop" } else { "-desktop" }
    $packageDisplaySuffix = if ($IsFull) { " full (Desktop)" } else { " (Desktop)" }
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
    # Note: models directory is NOT created in package
    # Models will be downloaded to C:\Users\Public\Owlangs\models\spacy at runtime
    
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
    
    # Copy spaCy models if they exist in source directory
    # Note: Models in installation directory are for reference only
    # Actual models should be downloaded to C:\Users\Public\Owlangs\models\spacy at runtime
    $modelsSourceDir = "3rdParty\spacy_models"
    $modelsPackageDir = "$packageRoot\models\spacy"
    if (Test-Path $modelsSourceDir) {
        $modelDirs = Get-ChildItem -Path $modelsSourceDir -Directory | Where-Object { 
            $_.Name -match '^[a-z]{2,3}_core_[a-z_]+_(sm|md|lg|trf)$' -and $_.Name -ne '__pycache__'
        }
        if ($modelDirs.Count -gt 0) {
            Write-Host "[$packageType] Copying spaCy models from source directory..." -ForegroundColor Yellow
            New-Item -ItemType Directory -Path $modelsPackageDir -Force | Out-Null
            foreach ($modelDir in $modelDirs) {
                $targetDir = Join-Path $modelsPackageDir $modelDir.Name
                Write-Host "[$packageType]   Copying $($modelDir.Name)..." -ForegroundColor Gray
                Copy-Item -Path $modelDir.FullName -Destination $targetDir -Recurse -Force
            }
            Write-Host "[$packageType] Copied $($modelDirs.Count) model(s) to package" -ForegroundColor Green
            Write-Host "[$packageType] Note: Models in package are for reference. Runtime models are stored in C:\Users\Public\Owlangs\models\spacy" -ForegroundColor Gray
        } else {
            Write-Host "[$packageType] No spaCy models found in source directory (models will be downloaded at runtime)" -ForegroundColor Gray
        }
    } else {
        Write-Host "[$packageType] spaCy models source directory not found (models will be downloaded at runtime)" -ForegroundColor Gray
    }
    
    # Redis binaries are NOT included in desktop version
    # Desktop version uses in-memory session storage (REDIS_ENABLED=false)
    # This reduces resource usage, simplifies deployment, and speeds up startup
    Write-Host "[$packageType] Skipping Redis binaries (desktop version uses in-memory sessions)" -ForegroundColor Gray
    
    # Copy Flutter Windows frontend build output
    # Flutter Windows builds to x64\runner\Release (architecture-specific path)
    $flutterWindowsBuildDir = "frontend\build\windows\x64\runner\Release"
    $flutterWindowsPackageDir = "$packageRoot\frontend"
    
    # Fallback to old path structure if x64 path doesn't exist
    if (-not (Test-Path $flutterWindowsBuildDir)) {
        $flutterWindowsBuildDir = "frontend\build\windows\runner\Release"
    }
    
    if (Test-Path $flutterWindowsBuildDir) {
        Write-Host "[$packageType] Copying Flutter Windows frontend from: $flutterWindowsBuildDir" -ForegroundColor Yellow
        New-Item -ItemType Directory -Path $flutterWindowsPackageDir -Force | Out-Null
        Copy-Item -Path "$flutterWindowsBuildDir\*" -Destination $flutterWindowsPackageDir -Recurse -Force
        Write-Host "[$packageType] Copied Flutter Windows frontend" -ForegroundColor Green
    } else {
        Write-Host "[$packageType] ERROR: Flutter Windows build directory not found!" -ForegroundColor Red
        Write-Host "[$packageType]   Tried: frontend\build\windows\x64\runner\Release" -ForegroundColor Yellow
        Write-Host "[$packageType]   Tried: frontend\build\windows\runner\Release" -ForegroundColor Yellow
        Write-Host "[$packageType]   Please run 'flutter build windows --release' first" -ForegroundColor Yellow
        return $false
    }
    
    # Build and copy Launcher
    Write-Host "[$packageType] Building Launcher..." -ForegroundColor Yellow
    $launcherBuildResult = Build-Launcher
    if ($launcherBuildResult -eq $false) {
        Write-Host "[$packageType] ERROR: Launcher build failed, cannot create package!" -ForegroundColor Red
        Write-Host "[$packageType]   Stopping package creation due to Launcher build failure." -ForegroundColor Red
        return $false
    }
    
    if ($launcherBuildResult -ne $true) {
        Write-Host "[$packageType] ERROR: Launcher build returned unexpected result: $launcherBuildResult" -ForegroundColor Red
        return $false
    }
    
    $launcherReleaseDir = "launcher\bin\Release\net8.0-windows"
    $launcherPackageDir = "$packageRoot\launcher"
    if (Test-Path $launcherReleaseDir) {
        Write-Host "[$packageType] Copying Launcher..." -ForegroundColor Yellow
        New-Item -ItemType Directory -Path $launcherPackageDir -Force | Out-Null
        
        # Copy Launcher files, excluding unnecessary files
        # Exclude: .pdb (debug symbols), .deps.json (dependency manifest), .xml (documentation), .rsp (response files), .pri (resource index)
        # Keep: .exe, .dll, .runtimeconfig.json, Resources, runtimes
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
        
        # Copy Resources directory if it exists (contains icon.ico)
        $resourcesSource = Join-Path $launcherReleaseDir "Resources"
        if (Test-Path $resourcesSource) {
            $resourcesDest = Join-Path $launcherPackageDir "Resources"
            New-Item -ItemType Directory -Path $resourcesDest -Force | Out-Null
            Copy-Item -Path "$resourcesSource\*" -Destination $resourcesDest -Recurse -Force
        }
        
        # Copy runtimes directory if it exists (contains native runtime files)
        $runtimesSource = Join-Path $launcherReleaseDir "runtimes"
        if (Test-Path $runtimesSource) {
            $runtimesDest = Join-Path $launcherPackageDir "runtimes"
            New-Item -ItemType Directory -Path $runtimesDest -Force | Out-Null
            Copy-Item -Path "$runtimesSource\*" -Destination $runtimesDest -Recurse -Force
        }
        
        Write-Host "[$packageType] Copied Launcher (excluded .pdb, .deps.json, .xml, and other unnecessary files)" -ForegroundColor Green
    } else {
        Write-Host "[$packageType] ERROR: Launcher release directory not found: $launcherReleaseDir" -ForegroundColor Red
        Write-Host "[$packageType]   This usually means the build failed even though no error was reported." -ForegroundColor Yellow
        return $false
    }
    
    # Copy configs directory (exclude secrets.json which is generated from template at runtime)
    $configSourceDir = Join-Path $RootDir "configs"
    if (Test-Path $configSourceDir) {
        Write-Host "[$packageType] Copying configs directory (excluding secrets.json)..." -ForegroundColor Yellow
        Copy-Item -Path "$configSourceDir\*" -Destination "$packageRoot\config" -Recurse -Force -Exclude "secrets.json"
        Write-Host "[$packageType] Copied configs" -ForegroundColor Green
    }
    
    # Note: Batch launcher (Owlangs-desktop.bat) is no longer needed
    # Users can start the application via:
    # 1. Desktop shortcut (points directly to OwlangsLauncher.exe)
    # 2. Direct execution of OwlangsLauncher.exe
    # 3. Start menu shortcut
    
    Write-Host "[$packageType] Package created: $packageRoot" -ForegroundColor Green
    return $true
}

# Main execution
Write-Host "Building Owlangs Windows Desktop Version package..." -ForegroundColor Green

if ($param1 -eq "--clean") {
    # Clean build artifacts
    Write-Host "Cleaning build artifacts..." -ForegroundColor Yellow
    $dirs = @("frontend\build\windows", "launcher\bin", "launcher\obj", "dist", "build", "build\win")
    foreach ($dir in $dirs) {
        if (Test-Path $dir) {
            Remove-Item -Path $dir -Recurse -Force -ErrorAction SilentlyContinue
            Write-Host "  Removed: $dir" -ForegroundColor Gray
        }
    }
    exit 0
}

# Determine what to build
$want_lite = $true
$want_full = $false
if ($param1 -eq "--full") {
    $want_lite = $false
    $want_full = $true
    Write-Host "Building FULL Desktop version only" -ForegroundColor Cyan
} else {
    Write-Host "Building LITE Desktop version only" -ForegroundColor Cyan
}

# Build Flutter Windows frontend
if (-not (Build-FlutterWindows)) {
    Write-Host "`n❌ BUILD FAILED: Flutter Windows build failed!" -ForegroundColor Red
    Write-Host "   Please fix the errors above and try again." -ForegroundColor Yellow
    exit 1
}

# Build download_models.exe
Write-Host "`n[build] Building download_models.exe..." -ForegroundColor Cyan
if (-not (Build-DownloadModels)) {
    Write-Host "`n❌ BUILD FAILED: download_models.exe build failed!" -ForegroundColor Red
    Write-Host "   Please fix the errors above and try again." -ForegroundColor Yellow
    exit 1
}

# Build backend with PyInstaller
$packageCreated = $false
if ($want_lite) {
    $version = Get-Version
    if (-not (Build-PyInstaller -SpecFile "lite.spec" -Version $version)) {
        Write-Host "`n❌ BUILD FAILED: Backend (PyInstaller) build failed!" -ForegroundColor Red
        Write-Host "   Please fix the errors above and try again." -ForegroundColor Yellow
        exit 1
    }
    
    if (Make-WinPackage-Desktop -Version $version -IsFull $false) {
        Write-Host "LITE Desktop package created successfully!" -ForegroundColor Green
        $packageCreated = $true
    } else {
        Write-Host "`n❌ BUILD FAILED: Package creation failed!" -ForegroundColor Red
        Write-Host "   Please fix the errors above and try again." -ForegroundColor Yellow
        exit 1
    }
}

if ($want_full) {
    $version = Get-Version
    if (-not (Build-PyInstaller -SpecFile "full.spec" -Version $version)) {
        Write-Host "`n❌ BUILD FAILED: Backend (PyInstaller) build failed!" -ForegroundColor Red
        Write-Host "   Please fix the errors above and try again." -ForegroundColor Yellow
        exit 1
    }
    
    if (Make-WinPackage-Desktop -Version $version -IsFull $true) {
        Write-Host "FULL Desktop package created successfully!" -ForegroundColor Green
        $packageCreated = $true
    } else {
        Write-Host "`n❌ BUILD FAILED: Package creation failed!" -ForegroundColor Red
        Write-Host "   Please fix the errors above and try again." -ForegroundColor Yellow
        exit 1
    }
}

if (-not $packageCreated) {
    Write-Host "`n❌ BUILD FAILED: No package was created!" -ForegroundColor Red
    exit 1
}

Write-Host "`nBuild completed!" -ForegroundColor Green
Write-Host "Desktop version packages are in: build\win\" -ForegroundColor Cyan

# Build NSIS installer if makensis is available
$makensisPath = Get-Command makensis -ErrorAction SilentlyContinue
if ($makensisPath) {
    Write-Host ""
    Write-Host "Building NSIS installer..." -ForegroundColor Cyan
    
    $version = Get-Version
    Write-Host "Building installer with version: $version" -ForegroundColor Cyan
    $packageNameSuffix = if ($want_full) { "-full-desktop" } else { "-desktop" }
    $packageDirName = "Owlangs$packageNameSuffix-$version"
    
    # Create installer output directory (absolute path)
    $installerDir = Join-Path $RootDir "build\installer"
    New-Item -ItemType Directory -Path $installerDir -Force | Out-Null
    # Include version number in installer filename
    $installerFileName = "Owlangs$packageNameSuffix-Installer-$version.exe"
    $installerOutput = Join-Path $installerDir $installerFileName
    
    Write-Host "[installer] Version: $version" -ForegroundColor Cyan
    Write-Host "[installer] Package suffix: $packageNameSuffix" -ForegroundColor Cyan
    Write-Host "[installer] Installer filename: $installerFileName" -ForegroundColor Cyan
    Write-Host "[installer] Installer output path: $installerOutput" -ForegroundColor Cyan
    
    # Update NSIS script with version and paths (write to temp file so repo installer.nsi is never modified)
    $nsisScript = "tools\build\installer.nsi"
    $nsisScriptGenerated = "tools\build\installer_generated.nsi"
    if (Test-Path $nsisScript) {
        $nsisContent = Get-Content $nsisScript -Raw
        $nsisContent = $nsisContent -replace '\$\{Version\}', $version
        $nsisContent = $nsisContent -replace '1\.0\.0', $version

        $installerOutEscaped = $installerOutput -replace '\\', '\\\\'
        Write-Host "[installer] Replacing @INSTALLER_OUT@ placeholder..." -ForegroundColor Cyan
        $nsisContent = $nsisContent -replace '@INSTALLER_OUT@', $installerOutEscaped

        # Use English license for installer to avoid garbled text on some systems
        $licenseFile = Join-Path $RootDir "LICENSE_EN.txt"
        if (-not (Test-Path $licenseFile)) { $licenseFile = Join-Path $RootDir "LICENSE" }
        if (Test-Path $licenseFile) {
            $licensePath = $licenseFile -replace '\\', '\\\\'
            $nsisContent = $nsisContent -replace '@LICENSE_FILE@', $licensePath
            Write-Host "Using LICENSE file: $licenseFile" -ForegroundColor Green
        } else {
            Write-Host "LICENSE file not found, removing license page from installer" -ForegroundColor Yellow
            $nsisContent = $nsisContent -replace '(?m)^; License page.*\r?\n', ''
            $nsisContent = $nsisContent -replace '(?m)^!insertmacro MUI_PAGE_LICENSE.*\r?\n', ''
        }

        $packageDir = Join-Path $RootDir "build\win\$packageDirName"
        if (Test-Path $packageDir) {
            $packagePath = $packageDir -replace '\\', '\\\\'
            $packagePathWithWildcard = "$packagePath\\*.*"
            $nsisContent = $nsisContent -replace '@PACKAGE_DIR@', $packagePathWithWildcard
            Write-Host "Using package directory: $packageDir" -ForegroundColor Green
        } else {
            Write-Host "WARNING: Package directory not found: $packageDir" -ForegroundColor Yellow
            if (Test-Path "build\win") {
                Get-ChildItem -Path "build\win" -Directory | ForEach-Object { Write-Host "     - $($_.Name)" -ForegroundColor Yellow }
            }
        }

        # Inject installer / uninstaller icon paths (use launcher icon)
        $iconFile = Join-Path $RootDir "launcher\Resources\icon.ico"
        if (Test-Path $iconFile) {
            $iconPathEscaped = $iconFile -replace '\\', '\\\\'
            $nsisContent = $nsisContent -replace '@INSTALLER_ICON@', $iconPathEscaped
            $nsisContent = $nsisContent -replace '@INSTALLER_UNICON@', $iconPathEscaped
            Write-Host "Using installer icon: $iconFile" -ForegroundColor Green
        } else {
            Write-Host "WARNING: Installer icon not found at $iconFile, NSIS will use default icons" -ForegroundColor Yellow
        }

        # Write to generated file only (repo installer.nsi is never touched)
        $nsisContent | Set-Content $nsisScriptGenerated -Encoding UTF8

        Push-Location $RootDir
        try {
            makensis $nsisScriptGenerated
            if ($LASTEXITCODE -eq 0) {
                Write-Host "NSIS installer built successfully!" -ForegroundColor Green
                Write-Host "Expected installer location: $installerOutput" -ForegroundColor Cyan
                if (Test-Path $installerOutput) {
                    Write-Host "✓ Installer file created at expected location with version number" -ForegroundColor Green
                } else {
                    Write-Host "✗ WARNING: Installer file not found at expected location!" -ForegroundColor Yellow
                    $altFiles = Get-ChildItem -Path $installerDir -Filter "*.exe" -ErrorAction SilentlyContinue
                    if ($altFiles) { $altFiles | ForEach-Object { Write-Host "     - $($_.Name)" -ForegroundColor Yellow } }
                }
            } else {
                Write-Host "WARNING: NSIS installer build failed (exit code: $LASTEXITCODE)" -ForegroundColor Yellow
            }
        } catch {
            Write-Host "WARNING: Failed to build NSIS installer: $_" -ForegroundColor Yellow
        } finally {
            Pop-Location
            if (Test-Path $nsisScriptGenerated) { Remove-Item $nsisScriptGenerated -Force }
        }
    } else {
        Write-Host "WARNING: NSIS script not found: $nsisScript" -ForegroundColor Yellow
    }
} else {
    Write-Host ""
    Write-Host "NOTE: NSIS installer not built (makensis not found in PATH)" -ForegroundColor Yellow
    Write-Host "      Install NSIS from https://nsis.sourceforge.io/ to generate installer" -ForegroundColor Yellow
    Write-Host "      Package directory is available at: build\win\$packageDirName" -ForegroundColor Cyan
}

