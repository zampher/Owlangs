# Download fonts script for Windows (PowerShell)
# Downloads Chinese, Korean, and Emoji fonts from Google Fonts

param(
    [string]$OutputDir = ""
)

Write-Host "=== Font Download Script ===" -ForegroundColor Cyan
Write-Host ""

# Check if Node.js is installed
$nodeVersion = node --version 2>$null
if (-not $nodeVersion) {
    Write-Host "Error: Node.js is not installed. Please install Node.js first." -ForegroundColor Red
    Write-Host "Download from: https://nodejs.org/" -ForegroundColor Yellow
    exit 1
}

Write-Host "Node.js version: $nodeVersion" -ForegroundColor Green

# Check if npx is available
$npxVersion = npx --version 2>$null
if (-not $npxVersion) {
    Write-Host "Error: npx is not available. Please ensure Node.js is properly installed." -ForegroundColor Red
    exit 1
}

Write-Host "npx version: $npxVersion" -ForegroundColor Green

# Fix npm directory issue if needed
$npmRoamingDir = "$env:APPDATA\npm"
if (-not (Test-Path $npmRoamingDir)) {
    Write-Host "Creating npm directory: $npmRoamingDir" -ForegroundColor Yellow
    New-Item -ItemType Directory -Path $npmRoamingDir -Force | Out-Null
}

Write-Host ""

# Determine output directory - use script location as base if not provided
if ([string]::IsNullOrEmpty($OutputDir)) {
    # Get script directory
    $scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
    # Go up one level from tools/ to project root
    $projectRoot = Split-Path -Parent $scriptDir
    $OutputDir = Join-Path $projectRoot "frontend\assets\fonts"
} elseif (-not [System.IO.Path]::IsPathRooted($OutputDir)) {
    # If relative path, resolve from current directory
    $currentDir = Get-Location
    # Check if we're in frontend directory
    if ($currentDir.Name -eq "frontend") {
        # If in frontend, go up one level first
        $projectRoot = Split-Path -Parent $currentDir
        $OutputDir = Join-Path $projectRoot $OutputDir
    } else {
        # Otherwise resolve normally
        $OutputDir = Join-Path $currentDir $OutputDir
    }
}

# Normalize path separators
$OutputDir = $OutputDir -replace '/', '\'

# Create output directory if it doesn't exist
if (-not (Test-Path $OutputDir)) {
    Write-Host "Creating output directory: $OutputDir" -ForegroundColor Yellow
    New-Item -ItemType Directory -Path $OutputDir -Force | Out-Null
}

# Get absolute path
$absoluteOutputDir = (Resolve-Path $OutputDir).Path
Write-Host "Output directory: $absoluteOutputDir" -ForegroundColor Cyan
Write-Host ""

# Download fonts using google-font-downloader
Write-Host "Downloading fonts..." -ForegroundColor Cyan
Write-Host "  - Roboto: 300, 400, 500, 700, 400i" -ForegroundColor White
Write-Host "  - Noto Sans SC (Chinese Simplified): 400" -ForegroundColor White
Write-Host "  - Noto Sans KR (Korean): 400" -ForegroundColor White
Write-Host "  - Noto Sans JP (Japanese): 400" -ForegroundColor White
Write-Host "  - Noto Sans: 400" -ForegroundColor White
Write-Host "  - Noto Color Emoji: 400" -ForegroundColor White
Write-Host ""

try {
    # Use --yes to auto-install package and --cache to avoid npm directory issues
    $env:NPX_CACHE_DIR = "$env:LOCALAPPDATA\npm-cache"
    if (-not (Test-Path $env:NPX_CACHE_DIR)) {
        New-Item -ItemType Directory -Path $env:NPX_CACHE_DIR -Force | Out-Null
    }
    
    # Build Google Fonts API URL
    # Format: https://fonts.googleapis.com/css?family=Font1:weights&family=Font2:weights
    # Note: In PowerShell, & must be escaped or URL must be quoted
    # We download all required fonts: Roboto, Noto Sans SC/KR/JP, Noto Sans, Noto Color Emoji
    $fontUrl = "https://fonts.googleapis.com/css?family=Roboto:300,400,500,700,400i&family=Noto+Sans+SC:400&family=Noto+Sans+KR:400&family=Noto+Sans+JP:400&family=Noto+Sans:400&family=Noto+Color+Emoji:400"
    
    Write-Host "Using Google Fonts URL: $fontUrl" -ForegroundColor Gray
    Write-Host ""
    
    # Download fonts by parsing CSS and downloading files directly
    Write-Host "Fetching font CSS..." -ForegroundColor Yellow
    try {
        # Use modern browser User-Agent to get WOFF2 format (if available)
        # Google Fonts returns different formats based on User-Agent
        $headers = @{
            "User-Agent" = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        $cssContent = Invoke-WebRequest -Uri $fontUrl -Headers $headers -UseBasicParsing | Select-Object -ExpandProperty Content
        
        # Parse CSS to extract font information and URLs
        # We need to match @font-face rules with their URLs to get font family, weight, and style
        $fontInfoList = @()
        
        # Extract @font-face blocks
        $fontFacePattern = '@font-face\s*\{[^}]*font-family:\s*[''"]?([^''";}]+)[''"]?[^}]*font-weight:\s*(\d+)[^}]*font-style:\s*(normal|italic)?[^}]*src:\s*url\(([^)]+)\)[^}]*\}'
        $fontFaceMatches = [regex]::Matches($cssContent, $fontFacePattern, [System.Text.RegularExpressions.RegexOptions]::IgnoreCase -bor [System.Text.RegularExpressions.RegexOptions]::Singleline)
        
        foreach ($match in $fontFaceMatches) {
            $family = $match.Groups[1].Value.Trim().Trim("'`"").Replace(' ', '')
            $weight = $match.Groups[2].Value
            $style = if ($match.Groups[3].Success) { $match.Groups[3].Value } else { "normal" }
            $url = $match.Groups[4].Value
            
            # Map weight number to name
            $weightName = switch ($weight) {
                "300" { "Light" }
                "400" { "Regular" }
                "500" { "Medium" }
                "700" { "Bold" }
                default { "Regular" }
            }
            
            # Map style
            $styleName = if ($style -eq "italic") { "Italic" } else { "" }
            
            # Create readable filename
            $extension = if ($url -match '\.woff2') { ".woff2" } elseif ($url -match '\.ttf') { ".ttf" } else { "" }
            if ($extension) {
                $readableName = "$family-$weightName"
                if ($styleName) {
                    $readableName += "-$styleName"
                }
                $readableName += $extension
                
                $fontInfoList += [PSCustomObject]@{
                    Url = $url
                    Family = $family
                    Weight = $weight
                    WeightName = $weightName
                    Style = $styleName
                    Extension = $extension
                    ReadableName = $readableName
                }
            }
        }
        
        # If regex parsing failed, fall back to simple URL extraction
        if ($fontInfoList.Count -eq 0) {
            Write-Host "  ⚠ Could not parse @font-face rules, using simple URL extraction" -ForegroundColor Yellow
            $woff2Urls = [regex]::Matches($cssContent, 'url\((https://fonts\.gstatic\.com/[^)]+\.woff2)\)') | ForEach-Object {
                $_.Groups[1].Value
            }
            $ttfUrls = [regex]::Matches($cssContent, 'url\((https://fonts\.gstatic\.com/[^)]+\.ttf)\)') | ForEach-Object {
                $_.Groups[1].Value
            }
            
            # Combine URLs, prioritizing WOFF2
            $fontUrls = @()
            $fontUrls += $woff2Urls
            $fontUrls += $ttfUrls
        } else {
            # Use parsed font information
            $fontUrls = $fontInfoList | ForEach-Object { $_.Url }
        }
        
        if ($fontUrls.Count -eq 0) {
            throw "No font URLs found in CSS"
        }
        
        if ($fontInfoList.Count -gt 0) {
            $woff2Count = ($fontInfoList | Where-Object { $_.Extension -eq ".woff2" }).Count
            $ttfCount = ($fontInfoList | Where-Object { $_.Extension -eq ".ttf" }).Count
            Write-Host "Found $($fontInfoList.Count) font files to download" -ForegroundColor Green
            Write-Host "  - WOFF2 files: $woff2Count (Web optimized)" -ForegroundColor Cyan
            Write-Host "  - TTF files: $ttfCount (Universal format)" -ForegroundColor Cyan
        } else {
            Write-Host "Found $($fontUrls.Count) font files to download" -ForegroundColor Green
        }
        Write-Host ""
        
        $downloadedCount = 0
        $skippedCount = 0
        
        # Create a lookup dictionary for font info
        $fontInfoMap = @{}
        foreach ($info in $fontInfoList) {
            $fontInfoMap[$info.Url] = $info
        }
        
        foreach ($fontUrlItem in $fontUrls) {
            try {
                # Extract filename from URL (last part after /)
                $uri = [System.Uri]$fontUrlItem
                $fileName = $uri.Segments[-1]
                
                # Remove query parameters if any
                if ($fileName.Contains('?')) {
                    $fileName = $fileName.Substring(0, $fileName.IndexOf('?'))
                }
                
                # Filter out dynamic subset fonts (Flutter doesn't need them)
                # These are typically:
                # - Files with hash-like names starting with 'KF' (Google Fonts dynamic subsets)
                #   Pattern: KF followed by 30+ alphanumeric/underscore/hyphen characters
                # - Files with very short names or unusual patterns
                # - Files that are subsets for specific unicode ranges
                if ($fileName -match '^KF[A-Z0-9_-]{30,}\.ttf$' -or 
                    $fileName -match '^[A-Z0-9]{30,}\.[0-9]+\.woff2$' -or
                    $fileName -match '\.(118|117|107|95|84|2)\.woff2$') {
                    Write-Host "  ⊘ Skipped (dynamic subset, not needed): $fileName" -ForegroundColor DarkGray
                    $skippedCount++
                    continue
                }
                
                # Sanitize filename - remove invalid characters
                $invalidChars = [System.IO.Path]::GetInvalidFileNameChars()
                foreach ($char in $invalidChars) {
                    $fileName = $fileName.Replace($char, '_')
                }
                
                # Try to get readable name from font info map (if available)
                $readableName = $fileName
                if ($fontInfoMap.ContainsKey($fontUrlItem)) {
                    $fontInfo = $fontInfoMap[$fontUrlItem]
                    $readableName = $fontInfo.ReadableName
                } else {
                    # Fallback: try to map hash-based filenames based on URL path
                    $fontExtension = [System.IO.Path]::GetExtension($fileName)
                    
                    if ($fontUrlItem -match '/s/([^/]+)/') {
                        $fontFamilySlug = $matches[1].ToLower()
                        $weight = "Regular"
                        $style = ""
                        
                        # Map font family slug to readable name
                        $familyMap = @{
                            "notosanssc" = "NotoSansSC"
                            "notosanskr" = "NotoSansKR"
                            "notosansjp" = "NotoSansJP"
                            "notosans" = "NotoSans"
                            "notocoloremoji" = "NotoColorEmoji"
                            "notosanssymbols" = "NotoSansSymbols"
                            "roboto" = "Roboto"
                        }
                        
                        # Determine weight from URL
                        if ($fontUrlItem -match 'Light|light|300') { $weight = "Light" }
                        elseif ($fontUrlItem -match 'Medium|medium|500') { $weight = "Medium" }
                        elseif ($fontUrlItem -match 'Bold|bold|700') { $weight = "Bold" }
                        elseif ($fontUrlItem -match 'Italic|italic') { $style = "Italic"; $weight = "Regular" }
                        
                        if ($familyMap.ContainsKey($fontFamilySlug)) {
                            $readableName = "$($familyMap[$fontFamilySlug])-$weight"
                            if ($style) {
                                $readableName += "-$style"
                            }
                            $readableName += $fontExtension
                        }
                    }
                }
                
                # Skip if file already exists (check both readable name and original filename)
                $destPath = Join-Path $absoluteOutputDir $readableName
                $originalDestPath = Join-Path $absoluteOutputDir $fileName
                
                if (Test-Path $destPath) {
                    Write-Host "  ⊘ Skipped (exists): $readableName" -ForegroundColor Gray
                    $skippedCount++
                    continue
                }
                if (Test-Path $originalDestPath) {
                    Write-Host "  ⊘ Skipped (exists): $fileName" -ForegroundColor Gray
                    $skippedCount++
                    continue
                }
                
                # Download font file
                if ($readableName -ne $fileName) {
                    Write-Host "  ↓ Downloading: $fileName -> $readableName" -ForegroundColor Cyan
                } else {
                    Write-Host "  ↓ Downloading: $fileName" -ForegroundColor Cyan
                }
                $tempFile = Join-Path $env:TEMP "font-$(Get-Random).tmp"
                
                try {
                    Invoke-WebRequest -Uri $fontUrlItem -OutFile $tempFile -UseBasicParsing
                    Move-Item -Path $tempFile -Destination $destPath -Force
                    Write-Host "    ✓ Downloaded: $readableName" -ForegroundColor Green
                    $downloadedCount++
                } catch {
                    Write-Host "    ✗ Failed: $($_.Exception.Message)" -ForegroundColor Red
                    if (Test-Path $tempFile) {
                        Remove-Item -Path $tempFile -Force -ErrorAction SilentlyContinue
                    }
                }
            } catch {
                Write-Host "  ✗ Error processing URL: $fontUrlItem" -ForegroundColor Red
                Write-Host "    $($_.Exception.Message)" -ForegroundColor Red
            }
        }
        
        Write-Host ""
        Write-Host "Download summary:" -ForegroundColor Cyan
        Write-Host "  ✓ Downloaded: $downloadedCount files" -ForegroundColor Green
        if ($skippedCount -gt 0) {
            Write-Host "  ⊘ Skipped: $skippedCount files (already exist or dynamic subsets)" -ForegroundColor Gray
        }
        
        if ($downloadedCount -eq 0 -and $skippedCount -eq 0) {
            throw "No fonts were downloaded"
        }
    } catch {
        Write-Host "Error downloading fonts: $_" -ForegroundColor Red
        throw
    }

    Write-Host ""
    Write-Host "✓ Fonts downloaded successfully!" -ForegroundColor Green
    Write-Host ""
    Write-Host "Downloaded fonts:" -ForegroundColor Cyan
    Write-Host "  WOFF2 files:" -ForegroundColor Yellow
    Get-ChildItem -Path $absoluteOutputDir -Filter "*.woff2" -File | Sort-Object Name | ForEach-Object {
        $sizeKB = [math]::Round($_.Length / 1KB, 2)
        Write-Host "    - $($_.Name) ($sizeKB KB)" -ForegroundColor White
    }
    Write-Host "  TTF files:" -ForegroundColor Yellow
    Get-ChildItem -Path $absoluteOutputDir -Filter "*.ttf" -File | Sort-Object Name | ForEach-Object {
        $sizeKB = [math]::Round($_.Length / 1KB, 2)
        Write-Host "    - $($_.Name) ($sizeKB KB)" -ForegroundColor White
    }
} catch {
    Write-Host ""
    Write-Host "✗ Error downloading fonts: $_" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "=== Download Complete ===" -ForegroundColor Cyan

