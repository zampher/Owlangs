# Quick build script for debugging
# This script builds components quickly without packaging
# Usage:
#   .\tools\build_debug.ps1              # build all components
#   .\tools\build_debug.ps1 --backend    # build backend only
#   .\tools\build_debug.ps1 --launcher   # build launcher only
#   .\tools\build_debug.ps1 --flutter    # build Flutter Windows only
#   .\tools\build_debug.ps1 --web        # build Flutter Web only
#   .\tools\build_debug.ps1 --clean      # clean build artifacts

param(
    [string]$param1 = ""
)

$ErrorActionPreference = "Stop"

# Get script directory and project root
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RootDir = Split-Path -Parent (Split-Path -Parent $ScriptDir)
Set-Location $RootDir

Write-Host "=== Owlangs Debug Build ===" -ForegroundColor Cyan
Write-Host ""

# Determine what to build
$buildBackend = $true
$buildLauncher = $true
$buildFlutter = $true
$buildWeb = $true

if ($param1 -eq "--backend") {
    $buildLauncher = $false
    $buildFlutter = $false
    $buildWeb = $false
    Write-Host "Building BACKEND only" -ForegroundColor Yellow
} elseif ($param1 -eq "--launcher") {
    $buildBackend = $false
    $buildFlutter = $false
    $buildWeb = $false
    Write-Host "Building LAUNCHER only" -ForegroundColor Yellow
} elseif ($param1 -eq "--flutter") {
    $buildBackend = $false
    $buildLauncher = $false
    $buildWeb = $false
    Write-Host "Building FLUTTER WINDOWS only" -ForegroundColor Yellow
} elseif ($param1 -eq "--web") {
    $buildBackend = $false
    $buildLauncher = $false
    $buildFlutter = $false
    Write-Host "Building FLUTTER WEB only" -ForegroundColor Yellow
} elseif ($param1 -eq "--clean") {
    Write-Host "Cleaning build artifacts..." -ForegroundColor Yellow
    $cleanDirs = @("dist", "build", "frontend\build", "launcher\bin", "launcher\obj")
    foreach ($dir in $cleanDirs) {
        if (Test-Path $dir) {
            Remove-Item -Path $dir -Recurse -Force -ErrorAction SilentlyContinue
            Write-Host "  Removed: $dir" -ForegroundColor Gray
        }
    }
    Write-Host "✅ Clean completed!" -ForegroundColor Green
    exit 0
} else {
    Write-Host "Building ALL components" -ForegroundColor Yellow
}

Write-Host ""

# Build Flutter Web
if ($buildWeb) {
    Write-Host "[1/4] Building Flutter Web..." -ForegroundColor Cyan
    $frontendDir = "frontend"
    if (Test-Path $frontendDir) {
        Push-Location $frontendDir
        try {
            Write-Host "  Running: flutter pub get" -ForegroundColor Gray
            flutter pub get | Out-Null
            if ($LASTEXITCODE -ne 0) {
                Write-Host "  ERROR: flutter pub get failed!" -ForegroundColor Red
                throw "Flutter pub get failed"
            }

            Write-Host "  Running: flutter build web --release" -ForegroundColor Gray
            flutter build web --release --no-tree-shake-icons 2>&1 | Select-String -Pattern "error|Error|ERROR" | ForEach-Object { Write-Host "  $_" -ForegroundColor Red }
            
            if ($LASTEXITCODE -eq 0) {
                Write-Host "  ✅ Flutter Web built successfully!" -ForegroundColor Green
            } else {
                Write-Host "  ❌ Flutter Web build failed!" -ForegroundColor Red
            }
        } catch {
            Write-Host "  ❌ Flutter Web build error: $_" -ForegroundColor Red
        } finally {
            Pop-Location
        }
    } else {
        Write-Host "  ⚠️ Frontend directory not found, skipping" -ForegroundColor Yellow
    }
    Write-Host ""
}

# Build Flutter Windows
if ($buildFlutter) {
    Write-Host "[2/4] Building Flutter Windows..." -ForegroundColor Cyan
    $frontendDir = "frontend"
    if (Test-Path $frontendDir) {
        Push-Location $frontendDir
        try {
            Write-Host "  Running: flutter pub get" -ForegroundColor Gray
            flutter pub get | Out-Null
            if ($LASTEXITCODE -ne 0) {
                Write-Host "  ERROR: flutter pub get failed!" -ForegroundColor Red
                throw "Flutter pub get failed"
            }

            Write-Host "  Running: flutter build windows --release" -ForegroundColor Gray
            flutter build windows --release 2>&1 | Select-String -Pattern "error|Error|ERROR" | ForEach-Object { Write-Host "  $_" -ForegroundColor Red }
            
            if ($LASTEXITCODE -eq 0) {
                Write-Host "  ✅ Flutter Windows built successfully!" -ForegroundColor Green
                Write-Host "  Output: frontend\build\windows\runner\Release" -ForegroundColor Gray
            } else {
                Write-Host "  ❌ Flutter Windows build failed!" -ForegroundColor Red
            }
        } catch {
            Write-Host "  ❌ Flutter Windows build error: $_" -ForegroundColor Red
        } finally {
            Pop-Location
        }
    } else {
        Write-Host "  ⚠️ Frontend directory not found, skipping" -ForegroundColor Yellow
    }
    Write-Host ""
}

# Build Launcher
if ($buildLauncher) {
    Write-Host "[3/4] Building Launcher..." -ForegroundColor Cyan
    $launcherDir = "launcher"
    if (Test-Path $launcherDir) {
        $syncIconScript = Join-Path $ScriptDir "sync_launcher_icon.ps1"
        $null = & $syncIconScript -RootDir $RootDir
        
        # Check .NET SDK
        $dotnetVersion = dotnet --version 2>&1
        if ($LASTEXITCODE -ne 0) {
            Write-Host "  ❌ .NET SDK not found!" -ForegroundColor Red
            Write-Host "     Install .NET 8.0 SDK from https://dotnet.microsoft.com/download" -ForegroundColor Yellow
        } else {
            $versionParts = $dotnetVersion -split '\.'
            $majorVersion = [int]$versionParts[0]
            if ($majorVersion -lt 8) {
                Write-Host "  ❌ .NET SDK version $dotnetVersion is too old (need 8.0+)" -ForegroundColor Red
            } else {
                Push-Location $launcherDir
                try {
                    Write-Host "  Running: dotnet build -c Release" -ForegroundColor Gray
                    dotnet build -c Release 2>&1 | Select-String -Pattern "error|Error|ERROR|warning|Warning" | ForEach-Object { 
                        if ($_ -match "error|Error|ERROR") {
                            Write-Host "  $_" -ForegroundColor Red
                        } else {
                            Write-Host "  $_" -ForegroundColor Yellow
                        }
                    }
                    
                    if ($LASTEXITCODE -eq 0) {
                        Write-Host "  ✅ Launcher built successfully!" -ForegroundColor Green
                        Write-Host "  Output: launcher\bin\Release\net8.0-windows\OwlangsLauncher.exe" -ForegroundColor Gray
                    } else {
                        Write-Host "  ❌ Launcher build failed!" -ForegroundColor Red
                    }
                } catch {
                    Write-Host "  ❌ Launcher build error: $_" -ForegroundColor Red
                } finally {
                    Pop-Location
                }
            }
        }
    } else {
        Write-Host "  ⚠️ Launcher directory not found, skipping" -ForegroundColor Yellow
    }
    Write-Host ""
}

# Build Backend
if ($buildBackend) {
    Write-Host "[4/4] Building Backend..." -ForegroundColor Cyan
    
    # Check Python virtual environment
    if (-not (Test-Path ".venv")) {
        Write-Host "  ⚠️ Virtual environment not found, creating..." -ForegroundColor Yellow
        python -m venv .venv
    }
    
    # Activate virtual environment
    & ".venv\Scripts\Activate.ps1"
    
    # Install/upgrade PyInstaller
    Write-Host "  Installing PyInstaller..." -ForegroundColor Gray
    python -m pip install --upgrade pyinstaller | Out-Null
    
    # Get version
    try {
        $version = python -c "import backend; print(backend.__version__)" 2>&1
        if ($LASTEXITCODE -ne 0) {
            $version = "1.0.0.0"
        }
    } catch {
        $version = "1.0.0.0"
    }
    
    Write-Host "  Building version: $version" -ForegroundColor Gray
    
    # Build with PyInstaller
    $env:OWLANGS_VERSION = $version
    Write-Host "  Running: pyinstaller lite.spec --clean" -ForegroundColor Gray
    pyinstaller --clean lite.spec 2>&1 | Select-String -Pattern "error|Error|ERROR|WARNING" | ForEach-Object { 
        if ($_ -match "error|Error|ERROR") {
            Write-Host "  $_" -ForegroundColor Red
        } else {
            Write-Host "  $_" -ForegroundColor Yellow
        }
    }
    Remove-Item Env:\OWLANGS_VERSION -ErrorAction SilentlyContinue
    
    if (Test-Path "dist\Owlangs-win.exe") {
        Write-Host "  ✅ Backend built successfully!" -ForegroundColor Green
        Write-Host "  Output: dist\Owlangs-win.exe" -ForegroundColor Gray
    } else {
        Write-Host "  ❌ Backend build failed!" -ForegroundColor Red
    }
    Write-Host ""
}

Write-Host "=== Build Complete ===" -ForegroundColor Cyan
Write-Host ""
Write-Host "📦 Build outputs:" -ForegroundColor Yellow
if ($buildBackend) {
    $backendExe = Get-ChildItem -Path "dist" -Filter "Owlangs-*-win.exe" -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($backendExe) {
        Write-Host "  ✅ Backend:    $($backendExe.FullName)" -ForegroundColor Green
    } else {
        Write-Host "  ❌ Backend:    Not found" -ForegroundColor Red
    }
}
if ($buildLauncher) {
    $launcherExe = "launcher\bin\Release\net8.0-windows\OwlangsLauncher.exe"
    if (Test-Path $launcherExe) {
        Write-Host "  ✅ Launcher:   $launcherExe" -ForegroundColor Green
    } else {
        Write-Host "  ❌ Launcher:   Not found" -ForegroundColor Red
    }
}
if ($buildFlutter) {
    $flutterExe = "frontend\build\windows\runner\Release\frontend.exe"
    if (Test-Path $flutterExe) {
        Write-Host "  ✅ Flutter:    $flutterExe" -ForegroundColor Green
    } else {
        Write-Host "  ❌ Flutter:    Not found" -ForegroundColor Red
    }
}
if ($buildWeb) {
    $webDir = "frontend\build\web"
    if (Test-Path $webDir) {
        Write-Host "  ✅ Flutter Web: $webDir" -ForegroundColor Green
    } else {
        Write-Host "  ❌ Flutter Web: Not found" -ForegroundColor Red
    }
}
Write-Host ""

