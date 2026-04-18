# 共享构建函数库
# 所有打包脚本都应该导入此模块以确保一致性

# 获取项目根目录
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RootDir = Split-Path -Parent (Split-Path -Parent $ScriptDir)

# 获取版本号（统一版本获取逻辑）
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

# 统一的 Flutter Web 构建函数
function Build-FlutterWebUnified {
    param(
        [switch]$SkipClean = $false,
        [string]$CanvasKitPath = "/static/flutter-web/canvaskit/"
    )
    
    Write-Host "[frontend] Building Flutter Web..." -ForegroundColor Cyan
    
    $frontendDir = Join-Path $RootDir "frontend"
    if (-not (Test-Path $frontendDir)) {
        Write-Host "[frontend] ERROR: frontend directory not found!" -ForegroundColor Red
        return $false
    }
    
    Push-Location $frontendDir
    
    try {
        # Clean Flutter Web artifacts
        if (-not $SkipClean) {
            Write-Host "[frontend] Running: flutter clean" -ForegroundColor Yellow
            flutter clean
            if ($LASTEXITCODE -ne 0) {
                Write-Host "[frontend] WARNING: flutter clean failed, continuing..." -ForegroundColor Yellow
            }
        }
        
        # Install dependencies
        Write-Host "[frontend] Running: flutter pub get" -ForegroundColor Yellow
        flutter pub get
        if ($LASTEXITCODE -ne 0) {
            Write-Host "[frontend] ERROR: flutter pub get failed!" -ForegroundColor Red
            return $false
        }
        
        # Build Flutter Web
        Write-Host "[frontend] Running: flutter build web --release --no-tree-shake-icons" -ForegroundColor Yellow
        flutter build web --release --no-tree-shake-icons
        
        if ($LASTEXITCODE -ne 0) {
            Write-Host "[frontend] ERROR: Flutter Web build failed!" -ForegroundColor Red
            return $false
        }
        
        # Copy fonts
        $buildFontsDir = "build\web\assets\fonts"
        if (-not (Test-Path $buildFontsDir)) {
            New-Item -ItemType Directory -Path $buildFontsDir -Force | Out-Null
        }
        
        $sourceFontsDir = "fonts"
        if (Test-Path $sourceFontsDir) {
            Write-Host "[frontend] Copying fonts to build output..." -ForegroundColor Yellow
            $fontFiles = Get-ChildItem -Path $sourceFontsDir -File
            $copiedCount = 0
            foreach ($fontFile in $fontFiles) {
                $destPath = Join-Path $buildFontsDir $fontFile.Name
                Copy-Item -Path $fontFile.FullName -Destination $destPath -Force
                $copiedCount++
            }
            Write-Host "[frontend] Copied $copiedCount font(s)" -ForegroundColor Green
        }
        
        # Copy to backend static directory
        $backendStaticDir = "..\backend\static\flutter-web"
        Write-Host "[frontend] Copying to backend static directory..." -ForegroundColor Yellow
        
        New-Item -ItemType Directory -Path $backendStaticDir -Force | Out-Null
        Copy-Item -Path "build\web\*" -Destination $backendStaticDir -Recurse -Force
        
        # Fix CanvasKit path
        Write-Host "[frontend] Fixing CanvasKit path..." -ForegroundColor Yellow
        $indexHtmlPath = Join-Path $backendStaticDir "index.html"
        
        if (Test-Path $indexHtmlPath) {
            $content = Get-Content $indexHtmlPath -Raw
            $originalContent = $content
            
            # Check if already has canvasKitBaseUrl
            $ckPattern = "canvasKitBaseUrl:\s*['`"][^'`"]*['`"]"
            if ($content -match $ckPattern) {
                # Replace existing configuration
                $content = $content -replace $ckPattern, "canvasKitBaseUrl: '$CanvasKitPath'"
            } else {
                # Add canvasKitBaseUrl after fontFallbackBaseUrl
                $fbPattern = "(fontFallbackBaseUrl:\s*['`"/\w-]+/,)"
                $content = $content -replace $fbPattern, "`$1`n                canvasKitBaseUrl: '$CanvasKitPath',"
            }
            
            if ($content -ne $originalContent) {
                $content | Set-Content $indexHtmlPath -Encoding UTF8
                Write-Host "[frontend] ✓ CanvasKit path fixed: $CanvasKitPath" -ForegroundColor Green
            } else {
                Write-Host "[frontend] CanvasKit path already correct" -ForegroundColor Gray
            }
            
            # Verify the fix
            $verifyContent = Get-Content $indexHtmlPath -Raw
            $verifyPattern = "canvasKitBaseUrl:\s*['`"]$([regex]::Escape($CanvasKitPath))['`"]"
            if ($verifyContent -match $verifyPattern) {
                Write-Host "[frontend] ✓ CanvasKit path verified" -ForegroundColor Green
            } else {
                Write-Host "[frontend] ⚠ CanvasKit path may not be correctly set" -ForegroundColor Yellow
            }
        } else {
            Write-Host "[frontend] WARNING: index.html not found!" -ForegroundColor Yellow
        }
        
        Write-Host "[frontend] Flutter Web built successfully!" -ForegroundColor Green
        return $true
        
    } finally {
        Pop-Location
    }
}

# 验证 CanvasKit 配置
function Test-CanvasKitConfig {
    param([string]$IndexHtmlPath)
    
    if (-not (Test-Path $IndexHtmlPath)) {
        Write-Host "[verify] ERROR: index.html not found: $IndexHtmlPath" -ForegroundColor Red
        return $false
    }
    
    $content = Get-Content $IndexHtmlPath -Raw
    
    # Check for canvasKitBaseUrl
    $ckPattern = "canvasKitBaseUrl"
    if (-not ($content -match $ckPattern)) {
        Write-Host "[verify] ERROR: canvasKitBaseUrl not found in $IndexHtmlPath" -ForegroundColor Red
        return $false
    }
    
    # Check for fontFallbackBaseUrl
    $fbPattern = "fontFallbackBaseUrl"
    if (-not ($content -match $fbPattern)) {
        Write-Host "[verify] WARNING: fontFallbackBaseUrl not found in $IndexHtmlPath" -ForegroundColor Yellow
    }
    
    # Check if using Google CDN (should not happen)
    if ($content -match "www\.gstatic\.com" -and -not ($content -match "canvasKitBaseUrl")) {
        Write-Host "[verify] WARNING: Possible Google CDN reference without local override" -ForegroundColor Yellow
    }
    
    # Extract and display canvasKitBaseUrl value
    $ckValuePattern = "canvasKitBaseUrl:\s*['`"]([^'`"]+)['`"]"
    if ($content -match $ckValuePattern) {
        $ckPath = $matches[1]
        Write-Host "[verify] CanvasKit path: $ckPath" -ForegroundColor Gray
    }
    
    Write-Host "[verify] ✓ CanvasKit configuration valid" -ForegroundColor Green
    return $true
}

# 确保虚拟环境
function Ensure-BuildVenv {
    param([switch]$SkipDependencyCheck = $false)
    
    if (-not (Test-Path ".venv")) {
        Write-Host "[env] Creating virtual environment..." -ForegroundColor Yellow
        python -m venv .venv
    }
    
    Write-Host "[env] Activating virtual environment..." -ForegroundColor Yellow
    & ".venv\Scripts\Activate.ps1"
    
    Write-Host "[env] Upgrading pip..." -ForegroundColor Yellow
    python -m pip install --upgrade pip | Out-Null
    
    # Pin numpy for PyInstaller compatibility
    if (-not $SkipDependencyCheck) {
        Write-Host "[env] Checking numpy version..." -ForegroundColor Yellow
        $numpyInfo = python -m pip show numpy 2>&1
        if ($LASTEXITCODE -eq 0) {
            $versionLine = $numpyInfo | Select-String "^Version:"
            if ($versionLine) {
                $version = ($versionLine -split ":")[1].Trim()
                if ($version -ne "1.26.4") {
                    Write-Host "[env] Installing numpy==1.26.4..." -ForegroundColor Yellow
                    python -m pip install --force-reinstall 'numpy==1.26.4' | Out-Null
                } else {
                    Write-Host "[env] numpy version OK" -ForegroundColor Gray
                }
            }
        }
    }
    
    # Install PyInstaller
    Write-Host "[env] Installing PyInstaller..." -ForegroundColor Yellow
    python -m pip install pyinstaller | Out-Null
    
    return $true
}

# Note: This script is designed to be dot-sourced, not imported as a module.
# All functions defined above are automatically available in the caller's scope.
# Usage: . "$ScriptDir\build_common.ps1"
