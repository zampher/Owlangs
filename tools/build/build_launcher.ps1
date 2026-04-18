# Build Launcher only - Quick debug script
# Usage:
#   .\tools\build_launcher.ps1          # build in Release mode
#   .\tools\build_launcher.ps1 --debug # build in Debug mode
#   .\tools\build_launcher.ps1 --clean # clean build artifacts

param(
    [string]$param1 = ""
)

$ErrorActionPreference = "Stop"

# Set console output encoding to UTF-8 to avoid garbled Chinese characters in compiler warnings
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

# Get script directory and project root
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RootDir = Split-Path -Parent (Split-Path -Parent $ScriptDir)
Set-Location $RootDir

Write-Host "=== Building Owlangs Launcher ===" -ForegroundColor Cyan
Write-Host ""

# Handle clean
if ($param1 -eq "--clean") {
    Write-Host "Cleaning Launcher build artifacts..." -ForegroundColor Yellow
    $cleanDirs = @("launcher\bin", "launcher\obj")
    foreach ($dir in $cleanDirs) {
        if (Test-Path $dir) {
            Remove-Item -Path $dir -Recurse -Force -ErrorAction SilentlyContinue
            Write-Host "  Removed: $dir" -ForegroundColor Gray
        }
    }
    Write-Host "✅ Clean completed!" -ForegroundColor Green
    exit 0
}

# Determine build configuration
$buildConfig = if ($param1 -eq "--debug") { "Debug" } else { "Release" }
Write-Host "Build configuration: $buildConfig" -ForegroundColor Yellow
Write-Host ""

$launcherDir = "launcher"
if (-not (Test-Path $launcherDir)) {
    Write-Host "❌ ERROR: Launcher directory not found: $launcherDir" -ForegroundColor Red
    exit 1
}

# Sync icon from canonical Flutter Windows ICO
Write-Host "[1/3] Preparing icon file..." -ForegroundColor Cyan
$syncIconScript = Join-Path $ScriptDir "sync_launcher_icon.ps1"
$null = & $syncIconScript -RootDir $RootDir
Write-Host ""

# Check .NET SDK
Write-Host "[2/3] Checking .NET SDK..." -ForegroundColor Cyan
$dotnetVersion = dotnet --version 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "  ❌ ERROR: .NET SDK not found!" -ForegroundColor Red
    Write-Host ""
    Write-Host "  Please install .NET 8.0 SDK:" -ForegroundColor Yellow
    Write-Host "  https://dotnet.microsoft.com/download/dotnet/8.0" -ForegroundColor Cyan
    exit 1
}

$versionParts = $dotnetVersion -split '\.'
$majorVersion = [int]$versionParts[0]
if ($majorVersion -lt 8) {
    Write-Host "  ❌ ERROR: .NET SDK version $dotnetVersion is too old" -ForegroundColor Red
    Write-Host "  Required: .NET 8.0 or higher" -ForegroundColor Yellow
    Write-Host "  Current:  $dotnetVersion" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "  Please upgrade .NET SDK:" -ForegroundColor Yellow
    Write-Host "  https://dotnet.microsoft.com/download/dotnet/8.0" -ForegroundColor Cyan
    exit 1
}

Write-Host "  ✅ .NET SDK version: $dotnetVersion" -ForegroundColor Green
Write-Host ""

# Build Launcher
Write-Host "[3/3] Building Launcher..." -ForegroundColor Cyan
Push-Location $launcherDir
try {
    Write-Host "  Running: dotnet build -c $buildConfig" -ForegroundColor Gray
    Write-Host ""
    
    # Build and capture output with UTF-8 encoding
    $buildOutput = dotnet build -c $buildConfig 2>&1 | ForEach-Object {
        # Convert output to string with proper encoding handling
        if ($_ -is [System.Management.Automation.ErrorRecord]) {
            $_.ToString()
        } else {
            $_.ToString()
        }
    }
    $buildSuccess = $LASTEXITCODE -eq 0
    
    # Filter and display errors/warnings
    $hasErrors = $false
    $hasWarnings = $false
    
    foreach ($line in $buildOutput) {
        if ($line -match "error|Error|ERROR") {
            Write-Host "  $line" -ForegroundColor Red
            $hasErrors = $true
        } elseif ($line -match "warning|Warning|WARNING") {
            Write-Host "  $line" -ForegroundColor Yellow
            $hasWarnings = $true
        }
    }
    
    Write-Host ""
    
    if ($buildSuccess) {
        Write-Host "  ✅ Launcher built successfully!" -ForegroundColor Green
        Write-Host ""
        
        # Show output location
        $outputExe = "bin\$buildConfig\net8.0-windows\OwlangsLauncher.exe"
        if (Test-Path $outputExe) {
            $fullPath = (Resolve-Path $outputExe).Path
            Write-Host "  📦 Output: $fullPath" -ForegroundColor Cyan
            Write-Host ""
            Write-Host "  🚀 To run:" -ForegroundColor Yellow
            Write-Host "     $fullPath" -ForegroundColor Gray
        } else {
            Write-Host "  ⚠️ WARNING: Executable not found at expected location" -ForegroundColor Yellow
        }
    } else {
        Write-Host "  ❌ Launcher build failed!" -ForegroundColor Red
        Write-Host ""
        Write-Host "  Check the errors above for details." -ForegroundColor Yellow
        exit 1
    }
    
    if ($hasWarnings -and -not $hasErrors) {
        Write-Host "  ⚠️ Build completed with warnings" -ForegroundColor Yellow
    }
    
} catch {
    Write-Host "  ❌ Build error: $_" -ForegroundColor Red
    exit 1
} finally {
    Pop-Location
}

Write-Host ""
Write-Host "=== Build Complete ===" -ForegroundColor Cyan

