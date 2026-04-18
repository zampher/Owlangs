# Verify Owlangs build/package success. Dot-source and call Test-PackageBuildSuccess.
# Usage from build script:
#   . "$ScriptDir\verify_build.ps1"
#   if (-not (Test-PackageBuildSuccess -Edition Basic -Installer:$Installer)) { exit 1 }

param()

$ErrorActionPreference = "Stop"

# Get project root (caller must set $RootDir or we derive from script dir; we live in tools/build)
if (-not $RootDir) {
    $ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
    $RootDir = Split-Path -Parent (Split-Path -Parent $ScriptDir)
}

function Get-BuildVersion {
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
        $content = Get-Content (Join-Path $RootDir "backend\__init__.py") -Raw -ErrorAction SilentlyContinue
        if ($content -match '__version__\s*=\s*["'']([^"'']+)["'']') {
            return $matches[1]
        }
    } catch { }
    return "0.0.0"
}

# Verify that the built package or installer exists and has key artifacts.
# Returns $true if verification passes, $false otherwise (and writes errors to host).
function Test-PackageBuildSuccess {
    param(
        [Parameter(Mandatory = $true)]
        [ValidateSet("Basic", "Standard", "Pro", "Enterprise")]
        [string]$Edition,
        [switch]$Installer
    )

    $version = Get-BuildVersion
    if (-not $version) {
        Write-Host "Verify: Could not read version, skipping artifact check." -ForegroundColor Yellow
        return $true
    }

    $root = $RootDir
    if (-not (Test-Path $root)) {
        Write-Host "Verify: Root dir not found: $root" -ForegroundColor Red
        return $false
    }

    if ($Installer) {
        $installerDir = Join-Path $root "build\installer"
        # Pro build outputs no "Pro" in name: NSIS Owlangs-Installer-{ver}.exe, Inno Owlangs-Standard-{ver}-x64.exe
        $installerName = if ($Edition -eq "Pro") { "Owlangs-Installer-$version.exe" } else { "Owlangs-$Edition-$version-x64.exe" }
        $installerPath = Join-Path $installerDir $installerName
        if (Test-Path $installerPath) {
            $size = (Get-Item $installerPath).Length / 1MB
            Write-Host "Verify: Installer OK: $installerName ($([math]::Round($size, 2)) MB)" -ForegroundColor Green
            return $true
        }
        # Pro: also accept Inno output Owlangs-Standard-{ver}-x64.exe
        if ($Edition -eq "Pro") {
            $altName = "Owlangs-Standard-$version-x64.exe"
            $altPath = Join-Path $installerDir $altName
            if (Test-Path $altPath) {
                $size = (Get-Item $altPath).Length / 1MB
                Write-Host "Verify: Installer OK: $altName ($([math]::Round($size, 2)) MB)" -ForegroundColor Green
                return $true
            }
        }
        # Fallback: any exe matching Edition and version in name
        $verEscaped = [regex]::Escape($version)
        $pattern = if ($Edition -eq "Pro") { "Owlangs-(Installer-$verEscaped\.exe|Standard-.*$verEscaped.*\.exe)" } else { "Owlangs-$Edition-.*$verEscaped.*\.exe" }
        $anyInstaller = Get-ChildItem -Path $installerDir -Filter "*.exe" -ErrorAction SilentlyContinue | Where-Object { $_.Name -match $pattern }
        if ($anyInstaller) {
            Write-Host "Verify: Installer OK: $($anyInstaller.Name)" -ForegroundColor Green
            return $true
        }
        Write-Host "Verify: Installer not found: $installerPath" -ForegroundColor Red
        return $false
    }

    # Simple package: check package dir and key files
    # Enterprise uses full package, others use lite package
    $packageDirName = if ($Edition -eq "Enterprise") { "Owlangs-full-$version" } else { "Owlangs-$version" }
    $packageDir = Join-Path $root (Join-Path "build\win" $packageDirName)
    if (-not (Test-Path $packageDir)) {
        Write-Host "Verify: Package dir not found: $packageDir" -ForegroundColor Red
        return $false
    }

    # All editions use same backend exe name (fixed, no version) so Launcher can find it
    $backendExe = "Owlangs-win.exe"
    $binExe = Join-Path $packageDir (Join-Path "bin" $backendExe)
    $launcherExe = Join-Path $packageDir "launcher\OwlangsLauncher.exe"
    $hasBin = Test-Path $binExe
    $hasLauncher = Test-Path $launcherExe
    if ($hasBin -or $hasLauncher) {
        Write-Host "Verify: Package OK: $packageDirName (bin=$hasBin, launcher=$hasLauncher)" -ForegroundColor Green
        return $true
    }
    Write-Host "Verify: Package missing key artifacts: $packageDir (expected bin\$backendExe or launcher\OwlangsLauncher.exe)" -ForegroundColor Red
    return $false
}
