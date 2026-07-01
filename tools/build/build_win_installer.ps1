# Build Owlangs Windows Installer with Inno Setup
# Usage:
#   tools/build_win_installer.ps1                      # build both lite and full installers
#   tools/build_win_installer.ps1 -Lite                # build lite installer only
#   tools/build_win_installer.ps1 -Lite -NoSpacy       # build lite without spaCy models
#   tools/build_win_installer.ps1 -Frontend chrome      # Chrome/Web frontend only (default)
#   tools/build_win_installer.ps1 -Frontend windows    # Windows desktop frontend only
#   tools/build_win_installer.ps1 -Frontend both       # Windows + Chrome (both frontends)

param(
    [switch]$Lite,
    [switch]$Full,
    [switch]$NoSpacy,
    [switch]$IncludeAnonymize,
    [switch]$IncludePandoc,
    [ValidateSet("chrome", "windows", "both")]
    [string]$Frontend = "chrome",
    [ValidateSet("Basic", "Standard", "Pro", "Enterprise")]
    [string]$Edition = "Pro",
    [string]$InnoSetupPath = ""
)

$ErrorActionPreference = "Stop"

# Get script directory (tools/build) and project root
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RootDir = Split-Path -Parent (Split-Path -Parent $ScriptDir)
Set-Location $RootDir

Write-Host "Building Owlangs Windows Installer..." -ForegroundColor Green

# Sync version before building (same as build_win.ps1)
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

# Determine what to build (support -Lite/-Full and --lite/--full; -- may be parsed as positional)
$want_lite = $true
$want_full = $true
if ($Lite) {
    $want_full = $false
} elseif ($Full) {
    $want_lite = $false
} elseif ($args.Count -ge 1) {
    $first = $args[0] -replace '^--', ''
    if ($first -eq 'lite') {
        $want_full = $false
        Write-Host "Building LITE only (from positional argument)" -ForegroundColor Cyan
    } elseif ($first -eq 'full') {
        $want_lite = $false
        Write-Host "Building FULL only (from positional argument)" -ForegroundColor Cyan
    }
} elseif ($InnoSetupPath -eq 'lite') {
    $want_full = $false
    $InnoSetupPath = ''
    Write-Host "Building LITE only (from argument)" -ForegroundColor Cyan
} elseif ($InnoSetupPath -eq 'full') {
    $want_lite = $false
    $InnoSetupPath = ''
    Write-Host "Building FULL only (from argument)" -ForegroundColor Cyan
}
if (-not $want_full -and $want_lite) {
    Write-Host "Building LITE version only" -ForegroundColor Cyan
} elseif ($want_full -and -not $want_lite) {
    Write-Host "Building FULL version only" -ForegroundColor Cyan
} elseif ($want_lite -and $want_full) {
    Write-Host "Building BOTH lite and full versions" -ForegroundColor Cyan
}

# Find Inno Setup
function Find-InnoSetup {
    $possiblePaths = @(
        "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
        "${env:ProgramFiles}\Inno Setup 6\ISCC.exe",
        "${env:ProgramFiles(x86)}\Inno Setup 5\ISCC.exe",
        "${env:ProgramFiles}\Inno Setup 5\ISCC.exe",
        "C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
        "C:\Program Files\Inno Setup 6\ISCC.exe"
    )
    
    if ($InnoSetupPath -and (Test-Path $InnoSetupPath)) {
        return $InnoSetupPath
    }
    
    foreach ($path in $possiblePaths) {
        if (Test-Path $path) {
            return $path
        }
    }
    
    return $null
}

# Build Flutter Web frontend (required by lite.spec/full.spec: backend/static/flutter-web)
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
        if ($LASTEXITCODE -ne 0) { throw "Flutter clean failed" }
        Write-Host "[frontend] Running: flutter pub get" -ForegroundColor Yellow
        flutter pub get
        if ($LASTEXITCODE -ne 0) { throw "Flutter pub get failed" }
        Write-Host "[frontend] Running: flutter build web --release --no-tree-shake-icons" -ForegroundColor Yellow
        flutter build web --release --no-tree-shake-icons
        if ($LASTEXITCODE -ne 0) { throw "Flutter Web build failed" }
        $buildFontsDir = "build\web\assets\fonts"
        if (-not (Test-Path $buildFontsDir)) { New-Item -ItemType Directory -Path $buildFontsDir -Force | Out-Null }
        $sourceFontsDir = "fonts"
        if (Test-Path $sourceFontsDir) {
            $fontFiles = Get-ChildItem -Path $sourceFontsDir -File
            foreach ($fontFile in $fontFiles) {
                Copy-Item -Path $fontFile.FullName -Destination (Join-Path $buildFontsDir $fontFile.Name) -Force
            }
        }
        $backendStaticDir = "..\backend\static\flutter-web"
        New-Item -ItemType Directory -Path $backendStaticDir -Force | Out-Null
        Copy-Item -Path "build\web\*" -Destination $backendStaticDir -Recurse -Force
        Write-Host "[frontend] Flutter Web built and copied successfully!" -ForegroundColor Green
    } finally {
        Pop-Location
    }
}

# Ensure virtual environment and build executables
function Ensure-Venv {
    if (-not (Test-Path ".venv")) {
        Write-Host "[env] Creating virtual environment..." -ForegroundColor Yellow
        python -m venv .venv
    }
    
    Write-Host "[env] Activating virtual environment..." -ForegroundColor Yellow
    & ".venv\Scripts\Activate.ps1"
    
    Write-Host "[env] Upgrading pip..." -ForegroundColor Yellow
    python -m pip install --upgrade pip | Out-Null
    
    # Pin numpy to 1.26.4 (compatible with Python 3.12, stable with PyInstaller)
    # Check if numpy version needs fixing
    $oldErrorAction = $ErrorActionPreference
    $ErrorActionPreference = "SilentlyContinue"
    $numpyNeedsFix = $true
    try {
        $numpyInstalled = python -m pip show numpy 2>&1
        if ($LASTEXITCODE -eq 0) {
            $numpyVersionLine = $numpyInstalled | Select-String "^Version:"
            if ($numpyVersionLine) {
                $numpyVersion = ($numpyVersionLine -split ":")[1].Trim()
                if ($numpyVersion -eq "1.26.4") {
                    $numpyNeedsFix = $false
                }
            }
        }
    } finally {
        $ErrorActionPreference = $oldErrorAction
    }
    
    if ($numpyNeedsFix) {
        Write-Host "[env] Installing numpy==1.26.4 for stable PyInstaller builds (Py3.12 compatible)" -ForegroundColor Yellow
        python -m pip install --force-reinstall 'numpy==1.26.4' | Out-Null
    } else {
        Write-Host "[env] numpy version is OK (1.26.4), skipping fix" -ForegroundColor Gray
    }
    
    # Install project and PyInstaller after numpy is pinned
    Write-Host "[env] Installing project dependencies and PyInstaller..." -ForegroundColor Yellow
    python -m pip install . pyinstaller | Out-Null
}

# Get version (same fallback order as build_win.ps1)
function Get-Version {
    $oldErrorAction = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $version = python -c "import backend; print(backend.__version__)" 2>&1
        if ($LASTEXITCODE -eq 0 -and $version -and -not ($version -match "Error|Traceback")) {
            return $version.Trim()
        }
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
    } catch { }
    return "0.0.0"
}

# Build PyInstaller (use --clean for reproducible builds, set OWLANGS_VERSION)
function Build-PyInstaller {
    param($SpecFile, $Version)
    $env:OWLANGS_VERSION = $Version
    Write-Host "[build] pyinstaller -y --clean $SpecFile (version: $Version)" -ForegroundColor Yellow
    pyinstaller -y --clean $SpecFile
    Remove-Item Env:\OWLANGS_VERSION -ErrorAction SilentlyContinue
}

# Update Inno Setup script with current version
function Update-InnoScript {
    param($Version)
    
    $scriptPath = "tools\build\owlangs_installer.iss"
    if (-not (Test-Path $scriptPath)) {
        Write-Host "Error: Inno Setup script not found at $scriptPath" -ForegroundColor Red
        return $false
    }
    
    $content = Get-Content $scriptPath -Raw
    $content = $content -replace '#define MyAppVersion "[^"]*"', "#define MyAppVersion `"$Version`""
    # Backend exe uses fixed name (no version) for simpler version updates
    $content = $content -replace '#define MyAppExeName "Owlangs-[^"]*-win\.exe"', '#define MyAppExeName "Owlangs-win.exe"'
    $content = $content -replace '#define MyAppFullExeName "Owlangs[^"]*win\.exe"', '#define MyAppFullExeName "Owlangs-win.exe"'
    
    Set-Content $scriptPath $content -Encoding UTF8
    Write-Host "[installer] Updated Inno Setup script with version $Version" -ForegroundColor Green
    return $true
}

# Stage Typst CLI + offline packages for Inno Setup (typst_overlay PDF export)
function Stage-TypstForInstaller {
    $stageRoot = "build\installer_stage\3rdParty"
    $markerRoot = "build\installer_stage"
    if (Test-Path $markerRoot) {
        Remove-Item -Path (Join-Path $markerRoot ".typst_cli_staged") -Force -ErrorAction SilentlyContinue
        Remove-Item -Path (Join-Path $markerRoot ".typst_packages_staged") -Force -ErrorAction SilentlyContinue
    }
    $stageScript = Join-Path $ScriptDir "stage_typst_3rdparty.ps1"
    if (Test-Path $stageScript) {
        & $stageScript -Dest3rdPartyRoot $stageRoot -Label "installer" -Fetch
    } else {
        Write-Host "[installer] WARNING: stage_typst_3rdparty.ps1 not found" -ForegroundColor Yellow
    }
}

# Stage Pandoc and pdflatex for Inno Setup when -IncludePandoc is set (same layout as build_win.ps1)
function Stage-PandocForInstaller {
    $stageRoot = "build\installer_stage\3rdParty\windows"
    if (Test-Path $stageRoot) {
        Remove-Item -Path $stageRoot -Recurse -Force -ErrorAction SilentlyContinue
    }
    New-Item -ItemType Directory -Path $stageRoot -Force | Out-Null

    $pandocSourceBase = "3rdParty\windows"
    $pandocDirs = Get-ChildItem -Path $pandocSourceBase -Directory -Filter "pandoc-*" -ErrorAction SilentlyContinue
    if ($pandocDirs) {
        foreach ($d in $pandocDirs) {
            $dest = Join-Path $stageRoot $d.Name
            Write-Host "[installer] Staging Pandoc from $($d.Name)..." -ForegroundColor Yellow
            Copy-Item -Path $d.FullName -Destination $dest -Recurse -Force
        }
        Write-Host "[installer] Staged Pandoc for installer" -ForegroundColor Green
    } else {
        Write-Host "[installer] WARNING: -IncludePandoc set but no 3rdParty\windows\pandoc-* found. Place Pandoc there to bundle." -ForegroundColor Yellow
    }

    $pdflatexSource = "3rdParty\windows\pdflatex"
    if (Test-Path $pdflatexSource) {
        $pdflatexDest = Join-Path $stageRoot "pdflatex"
        Write-Host "[installer] Staging pdflatex (XeLaTeX) for installer..." -ForegroundColor Yellow
        Copy-Item -Path $pdflatexSource -Destination $pdflatexDest -Recurse -Force
        Write-Host "[installer] Staged pdflatex for installer" -ForegroundColor Green
    } else {
        Write-Host "[installer] WARNING: -IncludePandoc set but 3rdParty\windows\pdflatex not found." -ForegroundColor Yellow
    }
}

# Build installer with Inno Setup. Output: Owlangs-{Edition}-{Version}-x64.exe
function Build-Installer {
    param($Version, [string]$EditionName = "Pro", [switch]$IncludePandocFiles)

    $innoSetup = Find-InnoSetup
    if (-not $innoSetup) {
        Write-Host "Error: Inno Setup not found. Please install Inno Setup or specify the path with -InnoSetupPath" -ForegroundColor Red
        Write-Host "Download from: https://jrsoftware.org/isinfo.php" -ForegroundColor Yellow
        return $false
    }

    Write-Host "[installer] Found Inno Setup at: $innoSetup" -ForegroundColor Green
    Write-Host "[installer] Edition: $EditionName -> Output: Owlangs-$EditionName-$Version-x64.exe" -ForegroundColor Cyan
    if ($EditionName -eq "Standard") {
        Write-Host "[installer] (Desktop build: no 'Pro' in name; same package for Standard and Pro by activation)" -ForegroundColor Gray
    }

    # Update script with current version
    if (-not (Update-InnoScript $Version)) {
        return $false
    }

    # Build installer (pass Edition so OutputBaseFilename=Owlangs-{Edition}-{Version}-x64)
    $scriptPath = Join-Path $RootDir "tools\build\owlangs_installer.iss"
    $scriptPathQuoted = "`"$scriptPath`""
    $isccArgs = @($scriptPathQuoted, "/DMyAppEdition=$EditionName")
    if ($IncludePandocFiles) {
        $isccArgs += "/DINCLUDE_PANDOC=1"
        Write-Host "[installer] Including Pandoc/pdflatex in installer (/DINCLUDE_PANDOC=1)" -ForegroundColor Cyan
    }

    Write-Host "[installer] Building installer with Inno Setup..." -ForegroundColor Yellow
    $process = Start-Process -FilePath $innoSetup -ArgumentList $isccArgs -Wait -PassThru -NoNewWindow -WorkingDirectory $RootDir

    if ($process.ExitCode -eq 0) {
        Write-Host "[installer] Installer built successfully!" -ForegroundColor Green
        return $true
    } else {
        Write-Host "[installer] Installer build failed with exit code: $($process.ExitCode)" -ForegroundColor Red
        return $false
    }
}

# Main execution
try {
    # Check if Inno Setup is available
    $innoSetup = Find-InnoSetup
    if (-not $innoSetup) {
        Write-Host "Inno Setup not found. Building simple package instead..." -ForegroundColor Yellow
        Write-Host "To build a proper installer, please install Inno Setup from: https://jrsoftware.org/isinfo.php" -ForegroundColor Yellow
        $buildParam = @()
        if ($want_lite -and -not $want_full) { $buildParam += "-Lite" } elseif ($want_full -and -not $want_lite) { $buildParam += "-Full" }
        if ($NoSpacy) {
            $env:OWLANGS_SKIP_SPACY = "1"
            Write-Host "Skipping spaCy models in package (OWLANGS_SKIP_SPACY=1)" -ForegroundColor Cyan
        }
        if ($IncludeAnonymize) { Write-Host "Including Anonymize (presidio/spacy and models)" -ForegroundColor Cyan }
        if ($IncludePandoc) { Write-Host "Including Pandoc/pdflatex for PDF workflow export" -ForegroundColor Cyan }
        try {
            & "$ScriptDir\build_win.ps1" @buildParam -Frontend $Frontend -IncludeAnonymize:$IncludeAnonymize -IncludePandoc:$IncludePandoc
        } finally {
            if ($NoSpacy) { Remove-Item Env:\OWLANGS_SKIP_SPACY -ErrorAction SilentlyContinue }
        }
        exit 0
    }
    
    Ensure-Venv
    $version = Get-Version
    Write-Host "Building version: $version" -ForegroundColor Cyan
    
    # Create output directories
    New-Item -ItemType Directory -Path "build\installer" -Force | Out-Null
    New-Item -ItemType Directory -Path "tools\build\windows" -Force | Out-Null
    
    # Build executables (set OWLANGS_INCLUDE_ANONYMIZE for lite when -IncludeAnonymize)
    if ($want_lite) {
        Write-Host "Building lite executable..." -ForegroundColor Yellow
        if ($IncludeAnonymize) { $env:OWLANGS_INCLUDE_ANONYMIZE = "1" }
        try {
            Build-PyInstaller "lite.spec"
        } finally {
            Remove-Item Env:\OWLANGS_INCLUDE_ANONYMIZE -ErrorAction SilentlyContinue
        }
    }
    
    if ($want_full) {
        Write-Host "Building full executable..." -ForegroundColor Yellow
        Build-PyInstaller "full.spec"
    }

    # Stage Typst + optional Pandoc/pdflatex for installer (Inno path)
    Stage-TypstForInstaller
    if ($IncludePandoc) {
        Write-Host "Including Pandoc/pdflatex in installer (staging for Inno Setup)..." -ForegroundColor Cyan
        Stage-PandocForInstaller
    }

    # Build installer: Pro uses no "Pro" in filename (compatible Standard/Pro); Enterprise keeps name
    $installerEditionName = if ($Edition -eq "Pro") { "Standard" } else { $Edition }
    if (Build-Installer $version -EditionName $installerEditionName -IncludePandocFiles:$IncludePandoc) {
        Write-Host "Windows installer build completed!" -ForegroundColor Green
        Write-Host "Installer is available in: build\installer\" -ForegroundColor Cyan
        
        # List generated installer EXE files
        $installerFiles = Get-ChildItem "build\installer\*.exe" -ErrorAction SilentlyContinue
        if ($installerFiles) {
            Write-Host "Generated installers and MD5 checksums:" -ForegroundColor Cyan
            foreach ($file in $installerFiles) {
                Write-Host "  - $($file.Name)" -ForegroundColor White
                try {
                    # Generate MD5 checksum file with same base name as installer
                    $hash = Get-FileHash -Path $file.FullName -Algorithm MD5
                    $md5Path = "$($file.FullName).md5"
                    $hash.Hash | Out-File -FilePath $md5Path -Encoding ASCII
                    Write-Host "    MD5: $($hash.Hash) -> $([System.IO.Path]::GetFileName($md5Path))" -ForegroundColor Gray
                } catch {
                    Write-Host "    Failed to generate MD5 file: $($_.Exception.Message)" -ForegroundColor Yellow
                }
            }
        }
    } else {
        Write-Host "Installer build failed!" -ForegroundColor Red
        exit 1
    }
    
} catch {
    Write-Host "Build failed: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}
