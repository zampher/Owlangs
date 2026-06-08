# Build Owlangs Windows installer package
# Usage:
#   tools/build_win.ps1                     # build both lite and full
#   tools/build_win.ps1 -Lite                # build lite only
#   tools/build_win.ps1 -Full                # build full only
#   tools/build_win.ps1 -Lite -IncludeAnonymize
#   tools/build_win.ps1 -Frontend chrome     # Chrome/Web only (default)
#   tools/build_win.ps1 -Frontend windows    # Windows desktop only
#   tools/build_win.ps1 -Frontend both       # Windows + Chrome
#   tools/build_win.ps1 -IncludePandoc       # bundle Pandoc + pdflatex for PDF workflow DOCX/PDF export
#   tools/build_win.ps1 -Clean               # clean build artifacts only

param(
    [switch]$Lite,
    [switch]$Full,
    [switch]$Clean,
    [ValidateSet("chrome", "windows", "both")]
    [string]$Frontend = "chrome",
    [switch]$IncludeAnonymize,
    [switch]$IncludePandoc,
    # Optional edition label for NSIS installer filename (e.g. Basic/Pro/Enterprise)
    [string]$Edition = "Basic"
)

$ErrorActionPreference = "Stop"

# Get script directory and project root
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RootDir = Split-Path -Parent (Split-Path -Parent $ScriptDir)
Set-Location $RootDir

# Sync version before building (skip if -Clean)
if (-not $Clean) {
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
}

# Clean build artifacts function
function Clean-BuildArtifacts {
    Write-Host "Cleaning build artifacts..." -ForegroundColor Yellow
    
    $cleanedItems = @()
    
    # Flutter Web build output
    $flutterBuildDir = "frontend\build\web"
    if (Test-Path $flutterBuildDir) {
        Write-Host "  Removing Flutter Web build: $flutterBuildDir" -ForegroundColor Gray
        Remove-Item -Path $flutterBuildDir -Recurse -Force -ErrorAction SilentlyContinue
        $cleanedItems += "Flutter Web build"
    }
    
    # PyInstaller build output
    $pyInstallerDirs = @("dist", "build")
    foreach ($dir in $pyInstallerDirs) {
        if (Test-Path $dir) {
            Write-Host "  Removing PyInstaller ${dir}: $dir" -ForegroundColor Gray
            Remove-Item -Path $dir -Recurse -Force -ErrorAction SilentlyContinue
            $cleanedItems += "PyInstaller ${dir}"
        }
    }
    
    # Package output directory
    $packageDir = "build\win"
    if (Test-Path $packageDir) {
        Write-Host "  Removing package output: $packageDir" -ForegroundColor Gray
        Remove-Item -Path $packageDir -Recurse -Force -ErrorAction SilentlyContinue
        $cleanedItems += "Package output"
    }
    
    # Flutter build cache (optional, more aggressive)
    $flutterBuildCache = "frontend\build"
    if (Test-Path $flutterBuildCache) {
        Write-Host "  Removing Flutter build cache: $flutterBuildCache" -ForegroundColor Gray
        Remove-Item -Path $flutterBuildCache -Recurse -Force -ErrorAction SilentlyContinue
        $cleanedItems += "Flutter build cache"
    }
    
    # PyInstaller spec files (keep the spec files, but remove .spec.bak if any)
    $specBakFiles = Get-ChildItem -Path "." -Filter "*.spec.bak" -ErrorAction SilentlyContinue
    foreach ($file in $specBakFiles) {
        Write-Host "  Removing backup spec file: $($file.Name)" -ForegroundColor Gray
        Remove-Item -Path $file.FullName -Force -ErrorAction SilentlyContinue
        $cleanedItems += "Backup spec files"
    }
    
    if ($cleanedItems.Count -eq 0) {
        Write-Host "  No build artifacts found to clean." -ForegroundColor Gray
    } else {
        Write-Host "Cleaned: $($cleanedItems.Count) item(s)" -ForegroundColor Green
    }
    
    Write-Host "Clean completed!" -ForegroundColor Green
    Write-Host ""
    Write-Host "Note: Python virtual environment (.venv) was NOT removed." -ForegroundColor Yellow
    Write-Host "      To clean the virtual environment, manually delete the .venv folder." -ForegroundColor Yellow
}

# Handle -Clean: only clean and exit
if ($Clean) {
    Clean-BuildArtifacts
    exit 0
}

Write-Host "Building Owlangs Windows package..." -ForegroundColor Green

# Determine what to build (-Lite / -Full; neither or both = build both)
$want_lite = $true
$want_full = $true
if ($Lite -and -not $Full) {
    $want_full = $false
    Write-Host "Building LITE version only" -ForegroundColor Cyan
} elseif ($Full -and -not $Lite) {
    $want_lite = $false
    Write-Host "Building FULL version only" -ForegroundColor Cyan
} else {
    Write-Host "Building BOTH lite and full versions" -ForegroundColor Cyan
}

# Frontend selection: chrome (Web only), windows (desktop only), both
$includeWindowsFrontend = ($Frontend -eq "windows" -or $Frontend -eq "both")
switch ($Frontend) {
    "chrome"  { Write-Host "Frontend: Chrome/Web only (backend serves Web UI)" -ForegroundColor Cyan }
    "windows" { Write-Host "Frontend: Windows desktop only" -ForegroundColor Cyan }
    "both"    { Write-Host "Frontend: Windows + Chrome (both)" -ForegroundColor Cyan }
}
# Anonymize option: when set, lite build includes presidio/spacy and copies spaCy models
if ($IncludeAnonymize) {
    Write-Host "Anonymize: included (presidio/spacy and spaCy models)" -ForegroundColor Cyan
} else {
    Write-Host "Anonymize: not included (smaller package)" -ForegroundColor Cyan
}
if ($IncludePandoc) {
    Write-Host "Pandoc/pdflatex: will be bundled for PDF workflow DOCX/PDF export" -ForegroundColor Cyan
} else {
    Write-Host "Pandoc/pdflatex: not bundled (use -IncludePandoc to include)" -ForegroundColor Gray
}

# Build Flutter Web frontend
function Build-FlutterWeb {
    Write-Host "[frontend] Building Flutter Web..." -ForegroundColor Cyan
    
    $frontendDir = "frontend"
    if (-not (Test-Path $frontendDir)) {
        Write-Host "[frontend] WARNING: frontend directory not found, skipping Flutter Web build" -ForegroundColor Yellow
        return
    }
    
    Push-Location $frontendDir
    
    try {
        # Clean Flutter Web artifacts to avoid stale package references
        Write-Host "[frontend] Running: flutter clean" -ForegroundColor Yellow
        flutter clean
        if ($LASTEXITCODE -ne 0) {
            Write-Host "[frontend] ERROR: flutter clean failed!" -ForegroundColor Red
            throw "Flutter clean failed"
        }

        # Ensure dependencies are up to date
        Write-Host "[frontend] Running: flutter pub get" -ForegroundColor Yellow
        flutter pub get
        if ($LASTEXITCODE -ne 0) {
            Write-Host "[frontend] ERROR: flutter pub get failed!" -ForegroundColor Red
            throw "Flutter pub get failed"
        }

        # Build Flutter Web
        Write-Host "[frontend] Running: flutter build web --release --no-tree-shake-icons" -ForegroundColor Yellow
        flutter build web --release --no-tree-shake-icons
        
        if ($LASTEXITCODE -ne 0) {
            Write-Host "[frontend] ERROR: Flutter Web build failed!" -ForegroundColor Red
            throw "Flutter Web build failed"
        }
        
        # Ensure fonts directory exists in build output
        $buildFontsDir = "build\web\assets\fonts"
        if (-not (Test-Path $buildFontsDir)) {
            New-Item -ItemType Directory -Path $buildFontsDir -Force | Out-Null
        }
        
        # Copy all fonts from frontend/fonts to build output (Flutter tree-shaking may remove unused fonts)
        $sourceFontsDir = "fonts"
        if (Test-Path $sourceFontsDir) {
            Write-Host "[frontend] Copying all fonts to build output (overwriting if exists)..." -ForegroundColor Yellow
            $fontFiles = Get-ChildItem -Path $sourceFontsDir -File
            $copiedCount = 0
            foreach ($fontFile in $fontFiles) {
                $destPath = Join-Path $buildFontsDir $fontFile.Name
                Copy-Item -Path $fontFile.FullName -Destination $destPath -Force
                $copiedCount++
                Write-Host "[frontend]   Copied: $($fontFile.Name)" -ForegroundColor Gray
            }
            Write-Host "[frontend] Fonts copied: $copiedCount files" -ForegroundColor Green
        } else {
            Write-Host "[frontend] WARNING: fonts directory not found: $sourceFontsDir" -ForegroundColor Yellow
        }
        
        # Copy to backend static directory
        $backendStaticDir = "..\backend\static\flutter-web"
        Write-Host "[frontend] Copying build output to $backendStaticDir..." -ForegroundColor Yellow
        
        # Ensure target directory exists
        New-Item -ItemType Directory -Path $backendStaticDir -Force | Out-Null
        
        # Copy all files (including canvaskit for local serving)
        Copy-Item -Path "build\web\*" -Destination $backendStaticDir -Recurse -Force
        
        # Fix base href and CanvasKit path using shared script
        $fixScript = Join-Path $ScriptDir "fix_canvaskit.ps1"
        if (Test-Path $fixScript) {
            & $fixScript -BackendStaticDir $backendStaticDir
        } else {
            Write-Host "[frontend] WARNING: fix_canvaskit.ps1 not found, skipping CanvasKit fix" -ForegroundColor Yellow
        }
        
        Write-Host "[frontend] Flutter Web built and copied successfully!" -ForegroundColor Green
    } finally {
        Pop-Location
    }
}

# Build Flutter Windows frontend
function Build-FlutterWindows {
    Write-Host "[frontend] Building Flutter Windows..." -ForegroundColor Cyan
    
    $frontendDir = "frontend"
    if (-not (Test-Path $frontendDir)) {
        Write-Host "[frontend] WARNING: frontend directory not found, skipping Flutter Windows build" -ForegroundColor Yellow
        return
    }
    
    Push-Location $frontendDir
    
    try {
        # Ensure dependencies are up to date
        Write-Host "[frontend] Running: flutter pub get" -ForegroundColor Yellow
        flutter pub get
        if ($LASTEXITCODE -ne 0) {
            Write-Host "[frontend] ERROR: flutter pub get failed!" -ForegroundColor Red
            throw "Flutter pub get failed"
        }

        # Build Flutter Windows
        Write-Host "[frontend] Running: flutter build windows --release" -ForegroundColor Yellow
        flutter build windows --release
        
        if ($LASTEXITCODE -ne 0) {
            Write-Host "[frontend] ERROR: Flutter Windows build failed!" -ForegroundColor Red
            throw "Flutter Windows build failed"
        }
        
        # Ensure fonts directory exists in build output (Flutter Windows may tree-shake fonts)
        # Flutter Windows builds to x64\runner\Release (architecture-specific path)
        $buildFontsDir = "build\windows\x64\runner\Release\data\flutter_assets\fonts"
        if (-not (Test-Path $buildFontsDir)) {
            # Fallback to old path structure
            $buildFontsDir = "build\windows\runner\Release\data\flutter_assets\fonts"
        }
        if (-not (Test-Path $buildFontsDir)) {
            New-Item -ItemType Directory -Path $buildFontsDir -Force | Out-Null
        }
        
        # Copy all fonts from frontend/fonts to build output (Flutter tree-shaking may remove unused fonts)
        # This is critical for translation software that needs to support all languages
        $sourceFontsDir = "fonts"
        if (Test-Path $sourceFontsDir) {
            Write-Host "[frontend] Copying all fonts to Windows build output (overwriting if exists)..." -ForegroundColor Yellow
            $fontFiles = Get-ChildItem -Path $sourceFontsDir -File
            $copiedCount = 0
            foreach ($fontFile in $fontFiles) {
                $destPath = Join-Path $buildFontsDir $fontFile.Name
                Copy-Item -Path $fontFile.FullName -Destination $destPath -Force
                $copiedCount++
                Write-Host "[frontend]   Copied: $($fontFile.Name)" -ForegroundColor Gray
            }
            Write-Host "[frontend] Fonts copied: $copiedCount files" -ForegroundColor Green
        } else {
            Write-Host "[frontend] WARNING: fonts directory not found: $sourceFontsDir" -ForegroundColor Yellow
        }
        
        Write-Host "[frontend] Flutter Windows built successfully!" -ForegroundColor Green
        Write-Host "[frontend] Build output: frontend\build\windows\runner\Release" -ForegroundColor Cyan
    } finally {
        Pop-Location
    }
}

# Helper function to check if a package version needs fixing
function Test-PackageVersion {
    param(
        [string]$PackageName,
        [string]$VersionConstraint
    )
    
    $oldErrorAction = $ErrorActionPreference
    $ErrorActionPreference = "SilentlyContinue"
    try {
        # Check if package is installed
        $installed = python -m pip show $PackageName 2>&1
        if ($LASTEXITCODE -ne 0) {
            return $true  # Package not installed, needs installation
        }
        
        # Get installed version
        $versionLine = $installed | Select-String "^Version:"
        if (-not $versionLine) {
            return $true  # Cannot determine version, assume needs fixing
        }
        
        $installedVersion = ($versionLine -split ":")[1].Trim()
        
        # Check if version matches constraint using pip's version checking
        $checkScript = @"
import packaging.version
import packaging.specifiers
try:
    installed = "$installedVersion"
    spec = packaging.specifiers.SpecifierSet("$VersionConstraint")
    if spec.contains(installed):
        print("OK")
    else:
        print("NEEDS_FIX")
except Exception as e:
    print("NEEDS_FIX")
"@
        $tempCheckScript = [System.IO.Path]::GetTempFileName() + ".py"
        $checkScript | Set-Content -Path $tempCheckScript -Encoding utf8 -NoNewline
        try {
            $result = python $tempCheckScript 2>&1
            if ($result -match "OK") {
                return $false  # Version is OK, no need to fix
            } else {
                return $true  # Version doesn't match, needs fixing
            }
        } finally {
            if (Test-Path $tempCheckScript) {
                Remove-Item $tempCheckScript -Force -ErrorAction SilentlyContinue
            }
        }
    } finally {
        $ErrorActionPreference = $oldErrorAction
    }
}

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
    
    # Clean up any corrupted package installations (e.g., ~illow from broken Pillow install)
    Write-Host "[env] Cleaning up corrupted package installations..." -ForegroundColor Yellow
    $corruptedDirs = Get-ChildItem ".venv\Lib\site-packages" -Directory -Filter "~*" -ErrorAction SilentlyContinue
    foreach ($dir in $corruptedDirs) {
        Write-Host "[env] Removing corrupted package directory: $($dir.Name)" -ForegroundColor Yellow
        Remove-Item -Path $dir.FullName -Recurse -Force -ErrorAction SilentlyContinue
    }
    
    # Check and fix version conflicts before installing project dependencies
    Write-Host "[env] Checking dependency version conflicts..." -ForegroundColor Yellow
    
    # Check and fix lxml version conflict (docling requires lxml<6.0.0)
    if (Test-PackageVersion -PackageName "lxml" -VersionConstraint "<6.0.0,>=5.4.0") {
        Write-Host "[env] Fixing lxml version (docling requires lxml<6.0.0)..." -ForegroundColor Yellow
        # Only uninstall if lxml is installed (avoids "Skipping lxml as it is not installed" on fresh CI)
        $null = python -m pip show lxml 2>&1
        if ($LASTEXITCODE -eq 0) {
            python -m pip uninstall -y lxml 2>&1 | Out-Null
        }
        # Temporarily disable error action to allow dependency conflict warnings
        $oldErrorAction = $ErrorActionPreference
        $ErrorActionPreference = "Continue"
        try {
            $lxmlOutput = python -m pip install --no-cache-dir 'lxml<6.0.0,>=5.4.0' 2>&1 | Tee-Object -Variable lxmlOutputVar
            # Check if installation actually succeeded (warnings are OK, but exit code 0 means success)
            if ($LASTEXITCODE -eq 0) {
                Write-Host "[env] lxml installed successfully" -ForegroundColor Green
            } else {
                Write-Host "[env] WARNING: lxml installation had issues (exit code: $LASTEXITCODE), but continuing..." -ForegroundColor Yellow
            }
            # Note dependency conflicts but don't fail
            if ($lxmlOutputVar -match "dependency conflicts") {
                Write-Host "[env] Note: Dependency conflict warnings detected (expected, non-fatal)" -ForegroundColor Gray
            }
        } finally {
            $ErrorActionPreference = $oldErrorAction
        }
    } else {
        Write-Host "[env] lxml version is OK, skipping fix" -ForegroundColor Gray
    }
    
    # Check and fix pillow version conflict (docling requires pillow<12.0.0,>=10.0.0)
    if (Test-PackageVersion -PackageName "pillow" -VersionConstraint "<12.0.0,>=10.0.0") {
        Write-Host "[env] Fixing pillow version (docling requires pillow<12.0.0,>=10.0.0)..." -ForegroundColor Yellow
        $null = python -m pip show pillow 2>&1
        if ($LASTEXITCODE -eq 0) {
            python -m pip uninstall -y pillow 2>&1 | Out-Null
        }
        $ErrorActionPreference = "Continue"
        try {
            $pillowOutput = python -m pip install --no-cache-dir 'pillow<12.0.0,>=10.0.0' 2>&1 | Tee-Object -Variable pillowOutputVar
            if ($LASTEXITCODE -eq 0) {
                Write-Host "[env] pillow installed successfully" -ForegroundColor Green
            } else {
                Write-Host "[env] WARNING: pillow installation had issues (exit code: $LASTEXITCODE), but continuing..." -ForegroundColor Yellow
            }
            if ($pillowOutputVar -match "dependency conflicts") {
                Write-Host "[env] Note: Dependency conflict warnings detected (expected, non-fatal)" -ForegroundColor Gray
            }
        } finally {
            $ErrorActionPreference = $oldErrorAction
        }
    } else {
        Write-Host "[env] pillow version is OK, skipping fix" -ForegroundColor Gray
    }
    
    # Check and fix svglib version conflict (svglib 1.6.0 requires lxml>=6.0.0, but we need lxml<6.0.0 for docling)
    # svglib is only used in development tools, so we can downgrade or remove it
    $svglibNeedsFix = $false
    $oldErrorAction3 = $ErrorActionPreference
    $ErrorActionPreference = "SilentlyContinue"
    try {
        $svglibInstalled = python -m pip show svglib 2>&1
        if ($LASTEXITCODE -eq 0) {
            $svglibVersionLine = $svglibInstalled | Select-String "^Version:"
            if ($svglibVersionLine) {
                $svglibVersion = ($svglibVersionLine -split ":")[1].Trim()
                # Check if version is >= 1.6.0
                $checkSvglibScript = @"
import packaging.version
try:
    installed = packaging.version.Version("$svglibVersion")
    required = packaging.version.Version("1.6.0")
    if installed >= required:
        print("NEEDS_FIX")
    else:
        print("OK")
except Exception:
    print("NEEDS_FIX")
"@
                $tempSvglibCheck = [System.IO.Path]::GetTempFileName() + ".py"
                $checkSvglibScript | Set-Content -Path $tempSvglibCheck -Encoding utf8 -NoNewline
                try {
                    $svglibResult = python $tempSvglibCheck 2>&1
                    if ($svglibResult -match "NEEDS_FIX") {
                        $svglibNeedsFix = $true
                    }
                } finally {
                    if (Test-Path $tempSvglibCheck) {
                        Remove-Item $tempSvglibCheck -Force -ErrorAction SilentlyContinue
                    }
                }
            } else {
                $svglibNeedsFix = $true
            }
        }
    } finally {
        $ErrorActionPreference = $oldErrorAction3
    }
    
    if ($svglibNeedsFix) {
        Write-Host "[env] Fixing svglib version conflict (downgrading to compatible version)..." -ForegroundColor Yellow
        $oldErrorAction3 = $ErrorActionPreference
        $ErrorActionPreference = "Continue"
        try {
            $svglibOutput = python -m pip install --force-reinstall 'svglib<1.6.0' 2>&1 | Tee-Object -Variable svglibOutputVar
            if ($LASTEXITCODE -eq 0) {
                Write-Host "[env] svglib downgraded successfully" -ForegroundColor Green
            } else {
                Write-Host "[env] svglib downgrade failed, uninstalling (not needed for production)..." -ForegroundColor Yellow
                python -m pip uninstall -y svglib 2>&1 | Out-Null
            }
            if ($svglibOutputVar -match "dependency conflicts") {
                Write-Host "[env] Note: svglib dependency conflict warnings (expected, non-fatal)" -ForegroundColor Gray
            }
        } finally {
            $ErrorActionPreference = $oldErrorAction3
        }
    } else {
        Write-Host "[env] svglib version is OK, skipping fix" -ForegroundColor Gray
    }
    
    # Check and fix numpy version (pin to 1.26.4 for stable PyInstaller builds)
    if (Test-PackageVersion -PackageName "numpy" -VersionConstraint "==1.26.4") {
        Write-Host "[env] Installing numpy==1.26.4 for stable PyInstaller builds (Py3.12 compatible)" -ForegroundColor Yellow
        $oldErrorAction4 = $ErrorActionPreference
        $ErrorActionPreference = "Continue"
        try {
            $numpyOutput = python -m pip install --force-reinstall 'numpy==1.26.4' 2>&1 | Tee-Object -Variable numpyOutputVar
            if ($LASTEXITCODE -eq 0) {
                Write-Host "[env] numpy installed successfully" -ForegroundColor Green
            }
            if ($numpyOutputVar -match "dependency conflicts") {
                Write-Host "[env] Note: numpy dependency conflict warnings (expected, non-fatal)" -ForegroundColor Gray
            }
        } finally {
            $ErrorActionPreference = $oldErrorAction4
        }
    } else {
        Write-Host "[env] numpy version is OK, skipping fix" -ForegroundColor Gray
    }
    
    # Install project dependencies (without installing the package itself)
    Write-Host "[env] Installing project dependencies from pyproject.toml..." -ForegroundColor Yellow
    $tempReq = [System.IO.Path]::GetTempFileName()
    $tempPyScript = [System.IO.Path]::GetTempFileName() + ".py"
    try {
        # Write Python script to temporary file to avoid PowerShell parsing issues
        $pyScriptContent = @'
import tomllib
import sys
from pathlib import Path
try:
    pyproject_path = Path("pyproject.toml")
    if not pyproject_path.exists():
        print("ERROR: pyproject.toml not found", file=sys.stderr)
        sys.exit(1)
    data = tomllib.loads(pyproject_path.read_text("utf-8"))
    deps = data.get("project", {}).get("dependencies", [])
    for dep in deps:
        print(dep)
except Exception as e:
    print("ERROR: Failed to read pyproject.toml: " + str(e), file=sys.stderr)
    sys.exit(1)
'@
        $pyScriptContent | Set-Content -Path $tempPyScript -Encoding utf8 -NoNewline
        
        $oldErrorAction5 = $ErrorActionPreference
        $ErrorActionPreference = "Continue"
        try {
            $pyOutput = python $tempPyScript 2>&1 | Tee-Object -Variable pyOutputVar
            if ($LASTEXITCODE -ne 0) {
                Write-Host "[env] ERROR: Failed to read pyproject.toml dependencies" -ForegroundColor Red
                Write-Host "[env] Output: $pyOutputVar" -ForegroundColor Red
                throw "Failed to generate requirements from pyproject.toml"
            }
            $pyOutput | Set-Content -Encoding utf8 $tempReq
            if ((Get-Item $tempReq).Length -eq 0) {
                Write-Host "[env] WARNING: No dependencies found in pyproject.toml" -ForegroundColor Yellow
            } else {
                Write-Host "[env] Installing dependencies from requirements file..." -ForegroundColor Yellow
                python -m pip install -r $tempReq 2>&1 | Out-Null
            }
        } finally {
            $ErrorActionPreference = $oldErrorAction5
        }
        
        # After installing dependencies, check and fix version conflicts again
        # (some dependencies might have upgraded lxml/pillow)
        Write-Host "[env] Re-checking version conflicts after dependency installation..." -ForegroundColor Yellow
        
        # Re-check and fix lxml if needed
        if (Test-PackageVersion -PackageName "lxml" -VersionConstraint "<6.0.0,>=5.4.0") {
            Write-Host "[env] Re-fixing lxml version..." -ForegroundColor Yellow
            $null = python -m pip show lxml 2>&1
            if ($LASTEXITCODE -eq 0) {
                python -m pip uninstall -y lxml 2>&1 | Out-Null
            }
            $oldErrorAction2 = $ErrorActionPreference
            $ErrorActionPreference = "Continue"
            try {
                $lxmlOutput2 = python -m pip install --no-cache-dir 'lxml<6.0.0,>=5.4.0' 2>&1 | Tee-Object -Variable lxmlOutputVar2
                if ($LASTEXITCODE -eq 0) {
                    Write-Host "[env] lxml re-installed successfully" -ForegroundColor Green
                }
                if ($lxmlOutputVar2 -match "dependency conflicts") {
                    Write-Host "[env] Note: lxml dependency conflict warnings (expected, non-fatal)" -ForegroundColor Gray
                }
            } finally {
                $ErrorActionPreference = $oldErrorAction2
            }
        } else {
            Write-Host "[env] lxml version is OK, skipping re-fix" -ForegroundColor Gray
        }
        
        # Re-check and fix pillow if needed
        if (Test-PackageVersion -PackageName "pillow" -VersionConstraint "<12.0.0,>=10.0.0") {
            Write-Host "[env] Re-fixing pillow version..." -ForegroundColor Yellow
            $null = python -m pip show pillow 2>&1
            if ($LASTEXITCODE -eq 0) {
                python -m pip uninstall -y pillow 2>&1 | Out-Null
            }
            $oldErrorAction2 = $ErrorActionPreference
            $ErrorActionPreference = "Continue"
            try {
                $pillowOutput2 = python -m pip install --no-cache-dir 'pillow<12.0.0,>=10.0.0' 2>&1 | Tee-Object -Variable pillowOutputVar2
                if ($LASTEXITCODE -eq 0) {
                    Write-Host "[env] pillow re-installed successfully" -ForegroundColor Green
                }
                if ($pillowOutputVar2 -match "dependency conflicts") {
                    Write-Host "[env] Note: pillow dependency conflict warnings (expected, non-fatal)" -ForegroundColor Gray
                }
            } finally {
                $ErrorActionPreference = $oldErrorAction2
            }
        } else {
            Write-Host "[env] pillow version is OK, skipping re-fix" -ForegroundColor Gray
        }
    } finally {
        if (Test-Path $tempReq) {
            Remove-Item $tempReq -Force -ErrorAction SilentlyContinue
        }
        if (Test-Path $tempPyScript) {
            Remove-Item $tempPyScript -Force -ErrorAction SilentlyContinue
        }
    }
    
    # Install PyInstaller
    Write-Host "[env] Installing PyInstaller..." -ForegroundColor Yellow
    python -m pip install pyinstaller | Out-Null
}

# Get version
function Get-Version {
    # Try to get version from backend module
    $oldErrorAction = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $version = python -c "import backend; print(backend.__version__)" 2>&1
        if ($LASTEXITCODE -eq 0 -and $version -and -not ($version -match "Error|Traceback")) {
            return $version.Trim()
        }
    } catch {
        # Fallback to pyproject.toml
    } finally {
        $ErrorActionPreference = $oldErrorAction
    }
    
    # Fallback: try to read from pyproject.toml
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
        # Final fallback
    }
    
    return "0.0.0"
}

# Build PyInstaller (OWLANGS_INCLUDE_ANONYMIZE=1 set by caller for lite when -IncludeAnonymize)
function Build-PyInstaller {
    param($SpecFile, $Version)
    $env:OWLANGS_VERSION = $Version
    Write-Host "[build] pyinstaller -y $SpecFile (version: $Version)" -ForegroundColor Yellow
    pyinstaller -y --clean $SpecFile
    Remove-Item Env:\OWLANGS_VERSION -ErrorAction SilentlyContinue
    Remove-Item Env:\OWLANGS_INCLUDE_ANONYMIZE -ErrorAction SilentlyContinue
}

# Create Windows installer package
function Make-WinPackage {
    param($Version, $IsFull = $false, $IncludeWindowsFrontend = $false, $IncludePandoc = $false)

    $packageType = if ($IsFull) { "full" } else { "lite" }
    $packageNameSuffix = if ($IsFull) { "-full" } else { "" }
    $packageDisplaySuffix = if ($IsFull) { " full" } else { "" }
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
    
    # Copy spaCy models: full build copies unless OWLANGS_SKIP_SPACY=1; lite copies only when -IncludeAnonymize
    $modelsSourceDir = "3rdParty\spacy_models"
    $modelsPackageDir = "$packageRoot\models\spacy"
    $skipSpacy = ($env:OWLANGS_SKIP_SPACY -eq "1") -or ((-not $IsFull) -and (-not $IncludeAnonymize))
    if ($skipSpacy) {
        if (-not $IsFull -and -not $IncludeAnonymize) {
            Write-Host "[$packageType] Skipping spaCy models (lite build without -IncludeAnonymize)" -ForegroundColor Cyan
        } elseif ($IsFull) {
            Write-Host "[$packageType] Skipping spaCy models (OWLANGS_SKIP_SPACY=1; download at runtime or use download_models)" -ForegroundColor Cyan
        } else {
            Write-Host "[$packageType] Skipping spaCy models (OWLANGS_SKIP_SPACY=1)" -ForegroundColor Cyan
        }
    } elseif (Test-Path $modelsSourceDir) {
        Write-Host "[$packageType] Copying spaCy models..." -ForegroundColor Yellow
        New-Item -ItemType Directory -Path $modelsPackageDir -Force | Out-Null
        
        # Copy all model directories (excluding Python scripts, cache, and test files)
        $modelDirs = Get-ChildItem -Path $modelsSourceDir -Directory | Where-Object { 
            # Include all spaCy model directories (typically named like: lang_core_*_sm/md/lg/trf)
            $_.Name -match '^[a-z]{2,3}_core_[a-z_]+_(sm|md|lg|trf)$' -and
            $_.Name -ne '__pycache__'
        }
        
        $copiedCount = 0
        foreach ($modelDir in $modelDirs) {
            $targetDir = Join-Path $modelsPackageDir $modelDir.Name
            Copy-Item -Path $modelDir.FullName -Destination $targetDir -Recurse -Force
            Write-Host "[$packageType] Copied model: $($modelDir.Name)" -ForegroundColor Green
            $copiedCount++
        }
        Write-Host "[$packageType] Copied $copiedCount model(s) to package" -ForegroundColor Green
    } else {
        Write-Host "[$packageType] WARNING: spaCy models directory not found: $modelsSourceDir" -ForegroundColor Yellow
    }

    # Copy Redis binaries/configs to package (exclude .pdb, .docx, and other non-runtime files)
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
        Write-Host "[$packageType] Copied Redis to package" -ForegroundColor Green
    } else {
        Write-Host "[$packageType] WARNING: Redis source directory not found: $redisSourceDir" -ForegroundColor Yellow
    }

    # Copy Pandoc and pdflatex (XeLaTeX) for PDF workflow DOCX/PDF export when -IncludePandoc is set
    if ($IncludePandoc) {
        $thirdPartyWindows = "$packageRoot\3rdParty\windows"
        if (-not (Test-Path $thirdPartyWindows)) {
            New-Item -ItemType Directory -Path $thirdPartyWindows -Force | Out-Null
        }
        $pandocSourceBase = "3rdParty\windows"
        # Copy pandoc-* directory (e.g. pandoc-3.1.11 with pandoc.exe inside)
        $pandocDirs = Get-ChildItem -Path $pandocSourceBase -Directory -Filter "pandoc-*" -ErrorAction SilentlyContinue
        if ($pandocDirs) {
            foreach ($d in $pandocDirs) {
                $dest = Join-Path $thirdPartyWindows $d.Name
                Write-Host "[$packageType] Copying Pandoc from $($d.Name)..." -ForegroundColor Yellow
                Copy-Item -Path $d.FullName -Destination $dest -Recurse -Force
                Write-Host "[$packageType] Copied Pandoc to package" -ForegroundColor Green
            }
        } else {
            Write-Host "[$packageType] WARNING: -IncludePandoc set but no 3rdParty\windows\pandoc-* folder found. Place Pandoc (e.g. pandoc-3.x.x with pandoc.exe) there to bundle." -ForegroundColor Yellow
        }
        # Copy pdflatex (TinyTeX layout: pdflatex\bin\windows\xelatex.exe) for PDF export
        $pdflatexSource = "3rdParty\windows\pdflatex"
        if (Test-Path $pdflatexSource) {
            $pdflatexDest = Join-Path $thirdPartyWindows "pdflatex"
            Write-Host "[$packageType] Copying pdflatex (XeLaTeX) for PDF export..." -ForegroundColor Yellow
            Copy-Item -Path $pdflatexSource -Destination $pdflatexDest -Recurse -Force
            Write-Host "[$packageType] Copied pdflatex to package" -ForegroundColor Green
        } else {
            Write-Host "[$packageType] WARNING: -IncludePandoc set but 3rdParty\windows\pdflatex not found. Run tools/install_pdflatex or place TinyTeX there to bundle." -ForegroundColor Yellow
        }
    } else {
        Write-Host "[$packageType] Pandoc/pdflatex: not included (use -IncludePandoc to bundle for PDF workflow DOCX/PDF export)" -ForegroundColor Gray
    }

    # Copy Flutter Windows frontend build output
    # Flutter Windows builds to x64\runner\Release (architecture-specific path)
    $flutterWindowsBuildDir = "frontend\build\windows\x64\runner\Release"
    
    # Fallback to old path structure if x64 path doesn't exist
    if (-not (Test-Path $flutterWindowsBuildDir)) {
        $flutterWindowsBuildDir = "frontend\build\windows\runner\Release"
    }
    
    $flutterWindowsPackageDir = "$packageRoot\frontend"
    if (Test-Path $flutterWindowsBuildDir) {
        Write-Host "[$packageType] Copying Flutter Windows frontend from: $flutterWindowsBuildDir" -ForegroundColor Yellow
        New-Item -ItemType Directory -Path $flutterWindowsPackageDir -Force | Out-Null
        Copy-Item -Path "$flutterWindowsBuildDir\*" -Destination $flutterWindowsPackageDir -Recurse -Force
        Write-Host "[$packageType] Copied Flutter Windows frontend to package" -ForegroundColor Green
    } else {
        Write-Host "[$packageType] WARNING: Flutter Windows build directory not found!" -ForegroundColor Yellow
        Write-Host "[$packageType]   Tried: frontend\build\windows\x64\runner\Release" -ForegroundColor Yellow
        Write-Host "[$packageType]   Tried: frontend\build\windows\runner\Release" -ForegroundColor Yellow
        Write-Host "[$packageType]         Run 'flutter build windows --release' first" -ForegroundColor Yellow
    }
    
    # Build and copy Launcher (C# .NET 8)
    $launcherDir = "launcher"
    $launcherPackageDir = "$packageRoot\launcher"
    if (Test-Path $launcherDir) {
        Write-Host "[$packageType] Building Launcher..." -ForegroundColor Yellow
        
        $syncIconScript = Join-Path $ScriptDir "sync_launcher_icon.ps1"
        & $syncIconScript -RootDir $RootDir | Out-Null
        
        # Check .NET SDK version
        $dotnetVersion = dotnet --version 2>&1
        if ($LASTEXITCODE -ne 0) {
            Write-Host "[$packageType] WARNING: .NET SDK not found. Launcher will not be built." -ForegroundColor Yellow
            Write-Host "[$packageType]         Install .NET 8.0 SDK from https://dotnet.microsoft.com/download" -ForegroundColor Yellow
        } else {
            $versionParts = $dotnetVersion -split '\.'
            $majorVersion = [int]$versionParts[0]
            if ($majorVersion -lt 8) {
                Write-Host "[$packageType] WARNING: .NET SDK version $dotnetVersion is too old. .NET 8.0 SDK is required." -ForegroundColor Yellow
                Write-Host "[$packageType]         Current version: $dotnetVersion" -ForegroundColor Yellow
                Write-Host "[$packageType]         Required version: 8.0 or higher" -ForegroundColor Yellow
                Write-Host "[$packageType]         Download from: https://dotnet.microsoft.com/download/dotnet/8.0" -ForegroundColor Yellow
            } else {
                Push-Location $launcherDir
                try {
                    # Build Launcher
                    dotnet build -c Release
                    if ($LASTEXITCODE -eq 0) {
                        # Copy Launcher executable and dependencies (excluding unnecessary files)
                        $launcherReleaseDir = "bin\Release\net8.0-windows"
                        if (Test-Path $launcherReleaseDir) {
                            New-Item -ItemType Directory -Path $launcherPackageDir -Force | Out-Null
                            
                            # Copy files, excluding unnecessary ones
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
                            
                            Write-Host "[$packageType] Copied Launcher to package (excluded .pdb, .deps.json, .xml, and other unnecessary files)" -ForegroundColor Green
                        } else {
                            Write-Host "[$packageType] WARNING: Launcher release directory not found: $launcherReleaseDir" -ForegroundColor Yellow
                        }
                    } else {
                        Write-Host "[$packageType] WARNING: Launcher build failed" -ForegroundColor Yellow
                    }
                } catch {
                    Write-Host "[$packageType] WARNING: Failed to build Launcher: $_" -ForegroundColor Yellow
                } finally {
                    Pop-Location
                }
            }
        }
    } elseif ($IncludeWindowsFrontend) {
        Write-Host "[$packageType] WARNING: Launcher directory not found: $launcherDir" -ForegroundColor Yellow
    } else {
        Write-Host "[$packageType] Skipping Launcher (Chrome/Web only)" -ForegroundColor Gray
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
    } else {
        Write-Host "[$packageType] WARNING: configs directory not found: $configSourceDir" -ForegroundColor Yellow
    }
    
    # Create Windows batch launcher
    $launcherName = if ($IsFull) { "Owlangs-full.bat" } else { "Owlangs.bat" }
    $launcherExeName = "OwlangsLauncher.exe"

    if ($IncludeWindowsFrontend) {
        # Start Launcher (backend + Windows desktop frontend)
        $launcherContent = @"
@echo off
setlocal

REM Start Owlangs Launcher (which manages backend and Flutter Windows frontend)
cd /d "%~dp0launcher"
if not exist "$launcherExeName" (
    echo ERROR: Launcher executable not found: $launcherExeName
    pause
    exit /b 1
)
echo Starting $packageDisplayName...
start "" "$launcherExeName"
"@
    } else {
        # Chrome/Web only: start backend exe with -i, user opens browser to localhost:8800
        $launcherContent = @"
@echo off
setlocal

REM Start Owlangs backend (Chrome/Web frontend: open http://localhost:8800 in browser)
cd /d "%~dp0bin"
if not exist "$exeName" (
    echo ERROR: Backend executable not found: $exeName
    pause
    exit /b 1
)
echo Starting $packageDisplayName backend...
echo Open http://localhost:8800 in Chrome or your browser.
"$exeName" -i
pause
"@
    }

    $launcherContent | Out-File -FilePath "$packageRoot\$launcherName" -Encoding ASCII
    
    # Create installation script
    $installScript = @"
@echo off
setlocal enabledelayedexpansion

echo Installing $packageDisplayName...

REM Create installation directory
set INSTALL_DIR=C:\Program Files\Owlangs\Document Agent
if not exist "%INSTALL_DIR%" (
    mkdir "%INSTALL_DIR%"
    echo Created installation directory: %INSTALL_DIR%
)

REM Copy files
xcopy /E /I /Y "%~dp0*" "%INSTALL_DIR%\"
echo Copied application files to %INSTALL_DIR%

REM Deploy pdflatex (TinyTeX/XeLaTeX) to ProgramData for write access.
REM It does not work reliably under C:\Program Files because XeLaTeX needs
REM to write fmt files and font caches at runtime.
set PDLATEX_SRC=%INSTALL_DIR%\3rdParty\windows\pdflatex
set PDLATEX_DST=C:\ProgramData\Owlangs\3rdParty\windows\pdflatex
if exist "%PDLATEX_SRC%\bin\windows\xelatex.exe" (
    if not exist "%PDLATEX_DST%\bin\windows\xelatex.exe" (
        echo Deploying pdflatex to ProgramData...
        powershell -NoProfile -Command "Copy-Item -Path '%PDLATEX_SRC%' -Destination '%PDLATEX_DST%' -Recurse -Force -ErrorAction SilentlyContinue"
        if exist "%PDLATEX_DST%\bin\windows\xelatex.exe" (
            echo pdflatex deployed to %PDLATEX_DST%
        ) else (
            echo WARNING: Failed to deploy pdflatex to ProgramData. PDF export may require admin rights.
        )
    )
)

REM Ensure Redis files are properly copied
if exist "%INSTALL_DIR%\3rdParty\windows\Redis-x64-3.0.504\redis-server.exe" (
    echo ✅ Redis executable found in installation directory
) else (
    echo ❌ WARNING: Redis executable not found in installation directory
    echo Expected location: %INSTALL_DIR%\3rdParty\windows\Redis-x64-3.0.504\redis-server.exe
)

REM Prepare Windows public configuration directory
set CONFIG_DIR=C:\ProgramData\Owlangs
if not exist "%CONFIG_DIR%" (
    mkdir "%CONFIG_DIR%"
    echo Created configuration directory: %CONFIG_DIR%
)

REM Initialize runtime configuration files from templates
echo Initializing runtime configuration files from templates...

REM Check if config directory is writable
echo test > "%CONFIG_DIR%\test_write.tmp" 2>nul
if errorlevel 1 (
    echo ERROR: Cannot write to configuration directory: %CONFIG_DIR%
    echo Please run as Administrator or check directory permissions.
    pause
    exit /b 1
) else (
    del "%CONFIG_DIR%\test_write.tmp" >nul 2>&1
)

echo Template directory: %INSTALL_DIR%\config
echo Runtime directory: %CONFIG_DIR%

REM Copy new config structure templates to runtime directory
REM Copy system.json from template
if not exist "%CONFIG_DIR%\system.json" (
    if exist "%INSTALL_DIR%\config\system.json.template" (
        copy "%INSTALL_DIR%\config\system.json.template" "%CONFIG_DIR%\system.json" >nul
        if errorlevel 1 (
            echo WARNING: Failed to copy system.json template
        ) else (
            echo Created system.json from template
        )
    )
)

REM Copy platforms.json from template
if not exist "%CONFIG_DIR%\platforms.json" (
    if exist "%INSTALL_DIR%\config\platforms.json.template" (
        copy "%INSTALL_DIR%\config\platforms.json.template" "%CONFIG_DIR%\platforms.json" >nul
        if errorlevel 1 (
            echo WARNING: Failed to copy platforms.json template
        ) else (
            echo Created platforms.json from template
        )
    )
)

REM Copy secrets.json from template
if not exist "%CONFIG_DIR%\secrets.json" (
    if exist "%INSTALL_DIR%\config\secrets.json.template" (
        copy "%INSTALL_DIR%\config\secrets.json.template" "%CONFIG_DIR%\secrets.json" >nul
        if errorlevel 1 (
            echo WARNING: Failed to copy secrets.json template
        ) else (
            echo Created secrets.json from template
        )
    )
)

REM Copy local.json from template
if not exist "%CONFIG_DIR%\local.json" (
    if exist "%INSTALL_DIR%\config\local.json.template" (
        copy "%INSTALL_DIR%\config\local.json.template" "%CONFIG_DIR%\local.json" >nul
        if errorlevel 1 (
            echo WARNING: Failed to copy local.json template
        ) else (
            echo Created local.json from template
        )
    )
)

REM Copy app_config.json
if not exist "%CONFIG_DIR%\app_config.json" (
    if exist "%INSTALL_DIR%\config\templates\app_config.json" (
        copy "%INSTALL_DIR%\config\templates\app_config.json" "%CONFIG_DIR%\app_config.json" >nul
        if errorlevel 1 (
            echo WARNING: Failed to copy app_config.json template
        ) else (
            echo Created app_config.json from template
        )
    ) else if exist "%INSTALL_DIR%\config\app_config.json" (
        copy "%INSTALL_DIR%\config\app_config.json" "%CONFIG_DIR%\" >nul
        if errorlevel 1 (
            echo WARNING: Failed to copy app_config.json
        ) else (
            echo Copied app_config.json
        )
    ) else (
        echo WARNING: app_config.json not found in installation package
        echo Expected locations:
        echo   - %INSTALL_DIR%\config\templates\app_config.json
        echo   - %INSTALL_DIR%\config\app_config.json
    )
)

REM Copy local_users.json from template
if not exist "%CONFIG_DIR%\local_users.json" (
    if exist "%INSTALL_DIR%\config\local_users.json.template" (
        copy "%INSTALL_DIR%\config\local_users.json.template" "%CONFIG_DIR%\local_users.json" >nul
        if errorlevel 1 (
            echo WARNING: Failed to copy local_users.json template
        ) else (
            echo Created local_users.json from template
        )
    )
)

REM Copy local_users.json from template
if not exist "%CONFIG_DIR%\local_users.json" (
    if exist "%INSTALL_DIR%\config\templates\local_users.json.template" (
        copy "%INSTALL_DIR%\config\templates\local_users.json.template" "%CONFIG_DIR%\local_users.json" >nul
        if errorlevel 1 (
            echo WARNING: Failed to copy local_users.json template
        ) else (
            echo Created local_users.json from template
        )
    ) else (
        echo WARNING: local_users.json.template not found in installation package
    )
)

REM Copy spaCy models to deployment directory
echo.
echo Copying spaCy models to deployment directory...
set MODELS_SOURCE_DIR=%INSTALL_DIR%\models\spacy
set MODELS_DEPLOY_DIR=%CONFIG_DIR%\models\spacy

if exist "%MODELS_SOURCE_DIR%" (
    REM Create models directory if it doesn't exist
    if not exist "%MODELS_DEPLOY_DIR%" (
        mkdir "%MODELS_DEPLOY_DIR%"
        echo Created models directory: %MODELS_DEPLOY_DIR%
    )
    
    REM Copy each model directory (only replace if exists in package, don't delete user models)
    for /d %%M in ("%MODELS_SOURCE_DIR%\*") do (
        set "MODEL_NAME=%%~nxM"
        set "TARGET_MODEL=%MODELS_DEPLOY_DIR%\!MODEL_NAME!"
        
        REM Only copy if model exists in package
        if exist "%%M" (
            REM If target model exists, replace it (user can re-download if needed)
            if exist "!TARGET_MODEL!" (
                echo Replacing existing model: !MODEL_NAME!
                rmdir /S /Q "!TARGET_MODEL!" >nul 2>&1
            ) else (
                echo Installing model: !MODEL_NAME!
            )
            xcopy /E /I /Y "%%M" "!TARGET_MODEL!\" >nul 2>&1
            if errorlevel 1 (
                echo WARNING: Failed to copy model !MODEL_NAME!
            ) else (
                echo ✅ Successfully installed model: !MODEL_NAME!
            )
        )
    )
    echo spaCy models installation completed
) else (
    echo WARNING: spaCy models not found in installation package
    echo Expected location: %MODELS_SOURCE_DIR%
    echo Models will need to be downloaded manually or placed in: %MODELS_DEPLOY_DIR%
)

echo Configuration files initialization completed.

REM Create desktop shortcut in Public Desktop so all users see it (when run as Admin, USERPROFILE points to Admin)
set DESKTOP=%PUBLIC%\Desktop
set SHORTCUT_NAME=$packageDisplayName.lnk
$($(if ($IncludeWindowsFrontend) { '' } else { "set EXE_NAME=$exeName`r`n" }))
REM Create shortcut using PowerShell
powershell -Command "`$WshShell = New-Object -comObject WScript.Shell; `$Shortcut = `$WshShell.CreateShortcut('%DESKTOP%\%SHORTCUT_NAME%'); `$Shortcut.TargetPath = '$(if ($IncludeWindowsFrontend) { '%INSTALL_DIR%\launcher\OwlangsLauncher.exe' } else { '%INSTALL_DIR%\bin\%EXE_NAME%' })'; `$Shortcut.WorkingDirectory = '$(if ($IncludeWindowsFrontend) { '%INSTALL_DIR%\launcher' } else { '%INSTALL_DIR%\bin' })'; `$Shortcut.Arguments = ''; `$Shortcut.Description = '$packageDisplayName'; `$Shortcut.Save()"

echo Created desktop shortcut: %SHORTCUT_NAME%

REM Create start menu shortcut (Public Start Menu so all users see it)
set START_MENU=%ProgramData%\Microsoft\Windows\Start Menu\Programs
if not exist "%START_MENU%\Owlangs" (
    mkdir "%START_MENU%\Owlangs"
)

powershell -Command "`$WshShell = New-Object -comObject WScript.Shell; `$Shortcut = `$WshShell.CreateShortcut('%START_MENU%\Owlangs\%SHORTCUT_NAME%'); `$Shortcut.TargetPath = '$(if ($IncludeWindowsFrontend) { '%INSTALL_DIR%\launcher\OwlangsLauncher.exe' } else { '%INSTALL_DIR%\bin\%EXE_NAME%' })'; `$Shortcut.WorkingDirectory = '$(if ($IncludeWindowsFrontend) { '%INSTALL_DIR%\launcher' } else { '%INSTALL_DIR%\bin' })'; `$Shortcut.Arguments = ''; `$Shortcut.Description = '$packageDisplayName'; `$Shortcut.Save()"

echo Created start menu shortcut

REM Register with Windows Programs and Features
echo Registering with Windows Programs and Features...
reg add "HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\Owlangs" /v "DisplayName" /t REG_SZ /d "$packageDisplayName" /f >nul 2>&1
reg add "HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\Owlangs" /v "DisplayVersion" /t REG_SZ /d "$Version" /f >nul 2>&1
reg add "HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\Owlangs" /v "Publisher" /t REG_SZ /d "Owlangs Team" /f >nul 2>&1
reg add "HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\Owlangs" /v "InstallLocation" /t REG_SZ /d "%INSTALL_DIR%" /f >nul 2>&1
reg add "HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\Owlangs" /v "UninstallString" /t REG_SZ /d "\"%INSTALL_DIR%\uninstall.bat\"" /f >nul 2>&1
reg add "HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\Owlangs" /v "DisplayIcon" /t REG_SZ /d "$(if ($IncludeWindowsFrontend) { '%INSTALL_DIR%\launcher\OwlangsLauncher.exe' } else { '%INSTALL_DIR%\bin\%EXE_NAME%' })" /f >nul 2>&1
reg add "HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\Owlangs" /v "NoModify" /t REG_DWORD /d 1 /f >nul 2>&1
reg add "HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\Owlangs" /v "NoRepair" /t REG_DWORD /d 1 /f >nul 2>&1
reg add "HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\Owlangs" /v "EstimatedSize" /t REG_DWORD /d 200000 /f >nul 2>&1
if errorlevel 1 (
    echo WARNING: Failed to register with Windows Programs and Features
    echo You may need to run as Administrator for proper registration
) else (
    echo Successfully registered with Windows Programs and Features
)

echo.
echo Installation completed!
echo.
echo Configuration files will be created at: C:\ProgramData\Owlangs
echo To start the application, run: %INSTALL_DIR%\$launcherName
echo Or use the desktop/start menu shortcuts.
echo.
echo You can now uninstall this program through:
echo - Control Panel > Programs and Features
echo - Or run: %INSTALL_DIR%\uninstall.bat
echo.
pause
"@
    
    $installScript | Out-File -FilePath "$packageRoot\install.bat" -Encoding ASCII
    
    # Create uninstall script
    $uninstallScript = @"
@echo off
setlocal

echo Uninstalling $packageDisplayName...

REM Remove Windows Programs and Features registration
echo Removing Windows Programs and Features registration...
reg delete "HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\Owlangs" /f >nul 2>&1
if errorlevel 1 (
    echo WARNING: Failed to remove Windows Programs and Features registration
    echo You may need to run as Administrator for proper cleanup
) else (
    echo Successfully removed Windows Programs and Features registration
)

REM Remove installation directory
set INSTALL_DIR=C:\Program Files\Owlangs\Document Agent
if exist "%INSTALL_DIR%" (
    rmdir /S /Q "%INSTALL_DIR%"
    echo Removed installation directory: %INSTALL_DIR%
)

REM Remove desktop shortcut (created in Public Desktop)
set DESKTOP=%PUBLIC%\Desktop
set SHORTCUT_NAME=$packageDisplayName.lnk
if exist "%DESKTOP%\%SHORTCUT_NAME%" (
    del "%DESKTOP%\%SHORTCUT_NAME%"
    echo Removed desktop shortcut: %SHORTCUT_NAME%
)

set START_MENU=%ProgramData%\Microsoft\Windows\Start Menu\Programs\Owlangs
if exist "%START_MENU%\%SHORTCUT_NAME%" (
    del "%START_MENU%\%SHORTCUT_NAME%"
    echo Removed start menu shortcut
)

REM Remove start menu folder if empty
if exist "%START_MENU%" (
    rmdir "%START_MENU%" 2>nul
)

echo.
echo Uninstallation completed!
echo.
echo Note: Configuration files at C:\ProgramData\Owlangs were not removed.
echo You may delete them manually if no longer needed.
echo.
pause
"@
    
    $uninstallScript | Out-File -FilePath "$packageRoot\uninstall.bat" -Encoding ASCII
    
    # Create README
    $readmeContent = @"
$packageDisplayName - Windows Package

INSTALLATION:
1. Run install.bat as Administrator
2. The application will be installed to C:\Program Files\Owlangs\Document Agent
3. Configuration files will be created at C:\ProgramData\Owlangs
4. Desktop and Start Menu shortcuts will be created

USAGE:
- Start the application using the desktop shortcut or Start Menu
- Or run: C:\Program Files\Owlangs\Document Agent\$launcherName
- The application will start on port 8800 by default
- Access the web interface at: http://localhost:8800

CONFIGURATION:
- Configuration files are stored in: C:\ProgramData\Owlangs
- Edit these files to customize the application:
  - system.json: System settings (authentication, parsing engine, logging)
  - platforms.json: AI platform configurations
  - secrets.json: API keys and sensitive data
  - local.json: Local settings (LDAP, HTTPS, Redis)
  - app_config.json: Application configuration

UNINSTALLATION:
- Run uninstall.bat as Administrator
- This will remove the application but keep configuration files

VERSION: $Version
BUILD DATE: $(Get-Date -Format "yyyy-MM-dd HH:mm:ss")
"@
    
    $readmeContent | Out-File -FilePath "$packageRoot\README.txt" -Encoding UTF8
    
    Write-Host "[$packageType] Built Windows package: $packageRoot" -ForegroundColor Green
    return $true
}

# Main execution
try {
    # Build Flutter Web frontend (required: lite.spec/full.spec bundle backend/static/flutter-web)
    Build-FlutterWeb

    # Build Flutter Windows frontend only when Frontend is windows or both
    if ($includeWindowsFrontend) {
        Build-FlutterWindows
    } else {
        Write-Host "[frontend] Skipping Flutter Windows (Frontend=$Frontend)" -ForegroundColor Gray
    }

    # Setup virtual environment and install dependencies
    Ensure-Venv
    $version = Get-Version
    Write-Host "Building version: $version" -ForegroundColor Cyan
    
    New-Item -ItemType Directory -Path "build\win" -Force | Out-Null
    
    if ($want_lite) {
        Write-Host "Building lite package..." -ForegroundColor Yellow
        $litePackageDir = "build\win\Owlangs-$version"
        if (Test-Path $litePackageDir) {
            Remove-Item -Recurse -Force $litePackageDir
            Write-Host "[lite] Cleaned up existing lite package" -ForegroundColor Yellow
        }
        if ($IncludeAnonymize) { $env:OWLANGS_INCLUDE_ANONYMIZE = "1" }
        try {
            Build-PyInstaller "lite.spec" $version
        } finally {
            Remove-Item Env:\OWLANGS_INCLUDE_ANONYMIZE -ErrorAction SilentlyContinue
        }
        Make-WinPackage -Version $version -IsFull $false -IncludeWindowsFrontend $includeWindowsFrontend -IncludePandoc $IncludePandoc
    }

    if ($want_full) {
        Write-Host "Building full package..." -ForegroundColor Yellow
        # Clean up any existing full package
        $fullPackageDir = "build\win\Owlangs-full-$version"
        if (Test-Path $fullPackageDir) {
            Remove-Item -Recurse -Force $fullPackageDir
            Write-Host "[full] Cleaned up existing full package" -ForegroundColor Yellow
        }
        if ($IncludeAnonymize) { $env:OWLANGS_INCLUDE_ANONYMIZE = "1" }
        try {
            if (Test-Path "full.spec") {
                Build-PyInstaller "full.spec" $version
            } else {
                Write-Host "[full] Skipping PyInstaller (full.spec not found, reusing lite build's executable)" -ForegroundColor Yellow
            }
        } finally {
            Remove-Item Env:\OWLANGS_INCLUDE_ANONYMIZE -ErrorAction SilentlyContinue
        }
        Make-WinPackage -Version $version -IsFull $true -IncludeWindowsFrontend $false -IncludePandoc $IncludePandoc
    }
    
    Write-Host "Windows package build completed!" -ForegroundColor Green
    Write-Host "Packages are available in: build\win\" -ForegroundColor Cyan
    
    # Build NSIS installer if makensis is available
    $makensisPath = Get-Command makensis -ErrorAction SilentlyContinue
    if ($makensisPath) {
        Write-Host ""
        Write-Host "Building NSIS installer..." -ForegroundColor Cyan
        
        # Create installer output directory (absolute path)
        $installerDir = Join-Path $RootDir "build\installer"
        New-Item -ItemType Directory -Path $installerDir -Force | Out-Null
        # NSIS installer filename: no edition for Pro (same package as Standard when unactivated); Enterprise keeps name
        $editionSuffix = ""
        if ($Edition -eq "Enterprise") {
            $editionSuffix = "-$Edition"
        }
        $installerOutput = Join-Path $installerDir "Owlangs$editionSuffix-Installer-$version.exe"
        
        # Update NSIS script with version and paths (write to temp file so repo installer.nsi is never modified)
        $nsisScript = "tools\build\installer.nsi"
        $nsisScriptGenerated = "tools\build\installer_generated.nsi"
        if (Test-Path $nsisScript) {
            $nsisContent = Get-Content $nsisScript -Raw
            $nsisContent = $nsisContent -replace '\$\{Version\}', $version
            
            # Replace hardcoded version numbers in NSIS script
            $nsisContent = $nsisContent -replace '1\.0\.0', $version

            # Inject output file path
            $installerOutEscaped = $installerOutput -replace '\\', '\\\\'
            $nsisContent = $nsisContent -replace '@INSTALLER_OUT@', $installerOutEscaped
            
            # Use English license for installer to avoid garbled text; fallback to LICENSE
            $licenseFile = Join-Path $RootDir "LICENSE_EN.txt"
            if (-not (Test-Path $licenseFile)) { $licenseFile = Join-Path $RootDir "LICENSE" }
            if (Test-Path $licenseFile) {
                # Use absolute path for LICENSE file (escape backslashes for NSIS)
                $licensePath = $licenseFile -replace '\\', '\\\\'
                $nsisContent = $nsisContent -replace '@LICENSE_FILE@', $licensePath
                Write-Host "✅ Using LICENSE file: $licenseFile" -ForegroundColor Green
            } else {
                Write-Host "⚠️ LICENSE file not found at $licenseFile, removing license page from installer" -ForegroundColor Yellow
                # Remove license page line (including comment)
                $nsisContent = $nsisContent -replace '(?m)^; License page.*\r?\n', ''
                $nsisContent = $nsisContent -replace '(?m)^!insertmacro MUI_PAGE_LICENSE.*\r?\n', ''
            }
            
            # Replace package directory path with absolute path
            # Lite builds output to Owlangs-<version>, full builds to Owlangs-full-<version>
            $packageDirName = if ($want_full) { "Owlangs-full-$version" } else { "Owlangs-$version" }
            $packageDir = Join-Path $RootDir ("build\win\" + $packageDirName)
            if (Test-Path $packageDir) {
                # Use absolute path for package directory (escape backslashes for NSIS)
                $packagePath = $packageDir -replace '\\', '\\\\'
                $packagePathWithWildcard = "$packagePath\\*.*"
                $nsisContent = $nsisContent -replace '@PACKAGE_DIR@', $packagePathWithWildcard
                Write-Host "✅ Using package directory: $packageDir" -ForegroundColor Green
            }
            
            # Inject installer / uninstaller icon paths (use launcher icon)
            $iconFile = Join-Path $RootDir "launcher\Resources\icon.ico"
            if (Test-Path $iconFile) {
                $iconPathEscaped = $iconFile -replace '\\', '\\\\'
                $nsisContent = $nsisContent -replace '@INSTALLER_ICON@', $iconPathEscaped
                $nsisContent = $nsisContent -replace '@INSTALLER_UNICON@', $iconPathEscaped
                Write-Host "✅ Using installer icon: $iconFile" -ForegroundColor Green
            } else {
                Write-Host "⚠️ Installer icon not found at $iconFile, NSIS will use default icons" -ForegroundColor Yellow
            }
            # Backend exe name for shortcut fallback (Chrome-only build has no launcher); fixed name, no version
            $backendExeName = "Owlangs-win.exe"
            $nsisContent = $nsisContent -replace '@BACKEND_EXE_NAME@', $backendExeName
            if (-not (Test-Path $packageDir)) {
                Write-Host "⚠️ Package directory not found: $packageDir" -ForegroundColor Yellow
                Write-Host "   Available directories in build\win:" -ForegroundColor Yellow
                if (Test-Path "build\win") {
                    Get-ChildItem -Path "build\win" -Directory | ForEach-Object { Write-Host "     - $($_.Name)" -ForegroundColor Yellow }
                }
            }
            
            # Write to generated file only (repo installer.nsi is never touched)
            $nsisContent | Set-Content $nsisScriptGenerated -Encoding UTF8
            
            # Compile NSIS installer from generated script
            Push-Location $RootDir
            try {
                makensis $nsisScriptGenerated
                if ($LASTEXITCODE -eq 0) {
                    Write-Host "✅ NSIS installer built successfully!" -ForegroundColor Green
                    Write-Host "Installer location: $installerOutput" -ForegroundColor Cyan
                } else {
                    Write-Host "⚠️ NSIS installer build failed (exit code: $LASTEXITCODE)" -ForegroundColor Yellow
                }
            } catch {
                Write-Host "⚠️ Failed to build NSIS installer: $_" -ForegroundColor Yellow
            } finally {
                Pop-Location
                if (Test-Path $nsisScriptGenerated) { Remove-Item $nsisScriptGenerated -Force }
            }
        } else {
            Write-Host "⚠️ NSIS script not found: $nsisScript" -ForegroundColor Yellow
        }
    } else {
        Write-Host ""
        Write-Host "⚠️ NSIS (makensis) not found. Skipping installer build." -ForegroundColor Yellow
        Write-Host "   Install NSIS from https://nsis.sourceforge.io/ to build installer" -ForegroundColor Yellow
    }
    
} catch {
    Write-Host "Build failed: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}
