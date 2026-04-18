# Sync version number from backend/__init__.py to all files
# This script ensures version consistency across the entire project
# Usage:
#   .\tools\setup\sync_version.ps1                    # sync version from backend/__init__.py
#   .\tools\setup\sync_version.ps1 --check             # check if all files have matching version
#   .\tools\setup\sync_version.ps1 -BuildNumber 123    # CI: use 123 for pubspec +N and version.json build_number (env BUILD_NUMBER used if not set and present)

param(
    [string]$param1 = "",
    [string]$BuildNumber = ""   # optional; overrides build for pubspec and version.json only (e.g. Jenkins BUILD_NUMBER)
)

$ErrorActionPreference = "Stop"

# Get script directory (tools/setup) and project root
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RootDir = Split-Path -Parent (Split-Path -Parent $ScriptDir)
Set-Location $RootDir

# Get version from backend/__init__.py (single source of truth)
function Get-SourceVersion {
    $versionFile = "backend\__init__.py"
    if (-not (Test-Path $versionFile)) {
        Write-Host "ERROR: Version source file not found: $versionFile" -ForegroundColor Red
        exit 1
    }
    
    $content = Get-Content $versionFile -Raw
    # Match __version__ = "1.0.0.0" or __version__ = '1.0.0.0'
    if ($content -match '__version__\s*=\s*["'']([^"'']+)["'']') {
        return $matches[1]
    } else {
        Write-Host "ERROR: Could not extract version from $versionFile" -ForegroundColor Red
        exit 1
    }
}

# Extract version components (supports X.Y.Z or X.Y.Z.W e.g. 1.0.0.0)
function Get-VersionComponents {
    param([string]$version)
    
    # Match X.Y.Z or X.Y.Z.W, with optional -prerelease and +build
    if ($version -match '^(\d+)\.(\d+)\.(\d+)(?:\.(\d+))?(?:-([^+]+))?(?:\+(\d+))?$') {
        $major, $minor, $patch = $matches[1], $matches[2], $matches[3]
        $fourth = $matches[4]   # optional 4th segment (e.g. 1.0.0.0)
        $prerelease = $matches[5]
        $buildSuffix = $matches[6]
        # For pubspec: X.Y.Z+BUILD; use 4th segment as BUILD if present, else +suffix or 1
        $build = if ($buildSuffix) { [int]$buildSuffix } elseif ($fourth) { [int]$fourth } else { 1 }
        return @{
            Major = $major
            Minor = $minor
            Patch = $patch
            Prerelease = if ($prerelease) { $prerelease } else { $null }
            Build = $build
            Full = $version
        }
    } else {
        Write-Host "ERROR: Invalid version format: $version" -ForegroundColor Red
        exit 1
    }
}

# Update version in a file
function Update-FileVersion {
    param(
        [string]$FilePath,
        [string]$Pattern,
        [string]$Replacement,
        [string]$Description
    )
    
    if (-not (Test-Path $FilePath)) {
        Write-Host "WARNING: File not found: $FilePath" -ForegroundColor Yellow
        return $false
    }
    
    $content = Get-Content $FilePath -Raw -Encoding UTF8
    $originalContent = $content
    
    $content = $content -replace $Pattern, $Replacement
    
    if ($content -ne $originalContent) {
        Set-Content -Path $FilePath -Value $content -Encoding UTF8 -NoNewline
        Write-Host "  Updated: $Description" -ForegroundColor Green
        return $true
    } else {
        Write-Host "  No change: $Description" -ForegroundColor Gray
        return $false
    }
}

# Check version in a file
function Check-FileVersion {
    param(
        [string]$FilePath,
        [string]$Pattern,
        [string]$ExpectedVersion,
        [string]$Description
    )
    
    if (-not (Test-Path $FilePath)) {
        Write-Host "  MISSING: $Description" -ForegroundColor Yellow
        return $false
    }
    
    $content = Get-Content $FilePath -Raw
    if ($content -match $Pattern) {
        $foundVersion = $matches[1]
        if ($foundVersion -eq $ExpectedVersion) {
            Write-Host "  OK: $Description (version: $foundVersion)" -ForegroundColor Green
            return $true
        } else {
            Write-Host "  MISMATCH: $Description (found: $foundVersion, expected: $ExpectedVersion)" -ForegroundColor Red
            return $false
        }
    } else {
        Write-Host "  NOT FOUND: $Description (pattern not matched)" -ForegroundColor Yellow
        return $false
    }
}

# Main execution
$sourceVersion = Get-SourceVersion
$versionInfo = Get-VersionComponents -version $sourceVersion

# Resolve build number: explicit -BuildNumber, else env BUILD_NUMBER (CI), else from source version
$effectiveBuild = $versionInfo.Build
if ([string]::IsNullOrEmpty($BuildNumber) -and $env:BUILD_NUMBER) {
    $BuildNumber = $env:BUILD_NUMBER
}
if (-not [string]::IsNullOrEmpty($BuildNumber)) {
    $effectiveBuild = [int]$BuildNumber
    Write-Host "Using CI build number: $effectiveBuild" -ForegroundColor Cyan
}

Write-Host "=== Version Synchronization ===" -ForegroundColor Cyan
Write-Host "Source version: $sourceVersion" -ForegroundColor Yellow
Write-Host ""

if ($param1 -eq "--check") {
    Write-Host "Checking version consistency..." -ForegroundColor Cyan
    Write-Host ""
    
    $allMatch = $true
    
    # Check backend/__init__.py
    $allMatch = (Check-FileVersion -FilePath "backend\__init__.py" -Pattern '__version__\s*=\s*["'']([^"'']+)["'']' -ExpectedVersion $sourceVersion -Description "backend/__init__.py") -and $allMatch
    
    # configs/system.json no longer stores app_version; single source is backend/__init__.py only

    # Check frontend/pubspec.yaml (version format: X.Y.Z+BUILD)
    $pubspecVersion = "$($versionInfo.Major).$($versionInfo.Minor).$($versionInfo.Patch)+$effectiveBuild"
    # Match version: X.Y.Z+BUILD (multiline pattern)
    $allMatch = (Check-FileVersion -FilePath "frontend\pubspec.yaml" -Pattern '(?m)^version:\s*([^\s]+)' -ExpectedVersion $pubspecVersion -Description "frontend/pubspec.yaml") -and $allMatch
    
    # Check frontend/lib/app/app_config.dart
    $allMatch = (Check-FileVersion -FilePath "frontend\lib\app\app_config.dart" -Pattern "appVersion\s*=\s*['\`"]([^'\`"]+)['\`"]" -ExpectedVersion $sourceVersion -Description "frontend/lib/app/app_config.dart") -and $allMatch
    
    # Check frontend/lib/core/constants/app_constants.dart
    $allMatch = (Check-FileVersion -FilePath "frontend\lib\core\constants\app_constants.dart" -Pattern "appVersion\s*=\s*['\`"]([^'\`"]+)['\`"]" -ExpectedVersion $sourceVersion -Description "frontend/lib/core/constants/app_constants.dart") -and $allMatch
    
    # Check launcher/OwlangsLauncher.csproj
    $allMatch = (Check-FileVersion -FilePath "launcher\OwlangsLauncher.csproj" -Pattern '<Version>([^<]+)</Version>' -ExpectedVersion $sourceVersion -Description "launcher/OwlangsLauncher.csproj") -and $allMatch
    
    # Check launcher/Views/SplashWindow.xaml (version text)
    $allMatch = (Check-FileVersion -FilePath "launcher\Views\SplashWindow.xaml" -Pattern 'Text="Version ([^"]+)"' -ExpectedVersion $sourceVersion -Description "launcher/Views/SplashWindow.xaml") -and $allMatch
    
    # Launcher uses fixed backend exe name (Owlangs-win.exe), no version check needed
    
    # Check tools/installer.nsi (DisplayVersion)
    $allMatch = (Check-FileVersion -FilePath "tools\build\installer.nsi" -Pattern 'DisplayVersion"\s*"([^"]+)"' -ExpectedVersion $sourceVersion -Description "tools/build/installer.nsi (DisplayVersion)") -and $allMatch

    # Check menubar_macos.spec (macOS menu bar app)
    $shortVersion = "$($versionInfo.Major).$($versionInfo.Minor).$($versionInfo.Patch)"
    $allMatch = (Check-FileVersion -FilePath "menubar_macos.spec" -Pattern "'CFBundleShortVersionString':\s*'([^']*)'" -ExpectedVersion $shortVersion -Description "menubar_macos.spec (CFBundleShortVersionString)") -and $allMatch
    $allMatch = (Check-FileVersion -FilePath "menubar_macos.spec" -Pattern "'CFBundleVersion':\s*'([^']*)'" -ExpectedVersion $sourceVersion -Description "menubar_macos.spec (CFBundleVersion)") -and $allMatch

    # Check backend/static/flutter-web/version.json (version from source, build_number may be CI override)
    $versionJsonExpectedVersion = $sourceVersion
    if (-not (Test-Path "backend\static\flutter-web\version.json")) {
        $allMatch = $false
        Write-Host "  MISSING: backend/static/flutter-web/version.json" -ForegroundColor Yellow
    } else {
        $vjContent = Get-Content "backend\static\flutter-web\version.json" -Raw
        if ($vjContent -match '"version"\s*:\s*"([^"]+)"' -and $matches[1] -eq $versionJsonExpectedVersion) {
            if ($vjContent -match '"build_number"\s*:\s*"([^"]+)"') {
                if ($matches[1] -eq "$effectiveBuild") {
                    Write-Host "  OK: backend/static/flutter-web/version.json (version: $($matches[1]), build_number: $effectiveBuild)" -ForegroundColor Green
                } else {
                    Write-Host "  MISMATCH: backend/static/flutter-web/version.json build_number (found: $($matches[1]), expected: $effectiveBuild)" -ForegroundColor Red
                    $allMatch = $false
                }
            } else {
                Write-Host "  OK: backend/static/flutter-web/version.json (version: $versionJsonExpectedVersion)" -ForegroundColor Green
            }
        } else {
            $found = if ($vjContent -match '"version"\s*:\s*"([^"]+)"') { $matches[1] } else { "not found" }
            Write-Host "  MISMATCH: backend/static/flutter-web/version.json (found: $found, expected: $versionJsonExpectedVersion)" -ForegroundColor Red
            $allMatch = $false
        }
    }

    Write-Host ""
    if ($allMatch) {
        Write-Host "All files have matching version: $sourceVersion" -ForegroundColor Green
        exit 0
    } else {
        Write-Host "Version mismatch detected! Run .\tools\setup\sync_version.ps1 to sync." -ForegroundColor Red
        exit 1
    }
} else {
    Write-Host "Syncing version to all files..." -ForegroundColor Cyan
    Write-Host ""

    $updatedCount = 0

    # configs/system.json no longer stores app_version; single source is backend/__init__.py only

    # Update frontend/pubspec.yaml (version format: X.Y.Z+BUILD; use effectiveBuild for CI)
    $pubspecVersion = "$($versionInfo.Major).$($versionInfo.Minor).$($versionInfo.Patch)+$effectiveBuild"
    if (Update-FileVersion -FilePath "frontend\pubspec.yaml" -Pattern '(?m)^version:\s*[^\s]+' -Replacement "version: $pubspecVersion" -Description "frontend/pubspec.yaml") {
        $updatedCount++
    }
    
    # Update frontend/lib/app/app_config.dart
    if (Update-FileVersion -FilePath "frontend\lib\app\app_config.dart" -Pattern "appVersion\s*=\s*['`"][^'`"]+['`"]" -Replacement "appVersion = '$sourceVersion'" -Description "frontend/lib/app/app_config.dart") {
        $updatedCount++
    }
    
    # Update frontend/lib/core/constants/app_constants.dart
    if (Update-FileVersion -FilePath "frontend\lib\core\constants\app_constants.dart" -Pattern "appVersion\s*=\s*['`"][^'`"]+['`"]" -Replacement "appVersion = '$sourceVersion'" -Description "frontend/lib/core/constants/app_constants.dart") {
        $updatedCount++
    }
    
    # Update launcher/OwlangsLauncher.csproj
    if (Update-FileVersion -FilePath "launcher\OwlangsLauncher.csproj" -Pattern '<Version>[^<]+</Version>' -Replacement "<Version>$sourceVersion</Version>" -Description "launcher/OwlangsLauncher.csproj") {
        $updatedCount++
    }
    
    # Update launcher/Views/SplashWindow.xaml (version text)
    if (Update-FileVersion -FilePath "launcher\Views\SplashWindow.xaml" -Pattern 'Text="Version [^"]+"' -Replacement "Text=`"Version $sourceVersion`"" -Description "launcher/Views/SplashWindow.xaml") {
        $updatedCount++
    }
    
    # Backend exe uses fixed name Owlangs-win.exe (no version), no update needed
    
    # Update tools/installer.nsi (DisplayVersion)
    $nsiDisplayVersionReplacement = 'DisplayVersion" "' + $sourceVersion + '"'
    if (Update-FileVersion -FilePath "tools\build\installer.nsi" -Pattern 'DisplayVersion"\s*"[^"]+"' -Replacement $nsiDisplayVersionReplacement -Description "tools/build/installer.nsi (DisplayVersion)") {
        $updatedCount++
    }

    # Update menubar_macos.spec (macOS menu bar app bundle version)
    # CFBundleShortVersionString: X.Y.Z (no 4th segment)
    $shortVersion = "$($versionInfo.Major).$($versionInfo.Minor).$($versionInfo.Patch)"
    if (Update-FileVersion -FilePath "menubar_macos.spec" -Pattern "'CFBundleShortVersionString':\s*'[^']*'" -Replacement "'CFBundleShortVersionString': '$shortVersion'" -Description "menubar_macos.spec (CFBundleShortVersionString)") {
        $updatedCount++
    }
    # CFBundleVersion: X.Y.Z.W (with 4th segment)
    if (Update-FileVersion -FilePath "menubar_macos.spec" -Pattern "'CFBundleVersion':\s*'[^']*'" -Replacement "'CFBundleVersion': '$sourceVersion'" -Description "menubar_macos.spec (CFBundleVersion)") {
        $updatedCount++
    }

    # Generate backend/static/flutter-web/version.json from single source (for Flutter web / PWA)
    $versionJsonDir = "backend\static\flutter-web"
    $versionJsonPath = "$versionJsonDir\version.json"
    if (-not (Test-Path $versionJsonDir)) {
        New-Item -ItemType Directory -Path $versionJsonDir -Force | Out-Null
    }
    $versionJsonContent = @{ app_name = "owlangs"; version = $sourceVersion; build_number = "$effectiveBuild"; package_name = "owlangs" } | ConvertTo-Json -Compress
    $versionJsonContent | Set-Content -Path $versionJsonPath -Encoding UTF8 -NoNewline
    Write-Host "  Updated: $versionJsonPath" -ForegroundColor Green
    $updatedCount++

    Write-Host ""
    if ($updatedCount -gt 0) {
        Write-Host "Version synchronized to $updatedCount file(s)" -ForegroundColor Green
    } else {
        Write-Host "All files already have the correct version" -ForegroundColor Green
    }
    
    Write-Host ""
    Write-Host "Note: frontend/windows/runner/Runner.rc uses Flutter's version from pubspec.yaml" -ForegroundColor Gray
    Write-Host "      It will be automatically updated when Flutter builds." -ForegroundColor Gray
}

