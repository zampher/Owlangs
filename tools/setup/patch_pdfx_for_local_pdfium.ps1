# Patch pdfx plugin so it does not overwrite PDFIUM_URL when the parent (e.g. frontend/windows/CMakeLists.txt)
# has set it to a file:// URL (local 3rdParty tarball). Run once after 'flutter pub get'.
# Idempotent: safe to run multiple times.

$ErrorActionPreference = "Stop"
$RootDir = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$FrontendDir = Join-Path $RootDir "frontend"

# Resolve pub cache: prefer FLUTTER_ROOT from env, else use same cache as 'flutter pub get'
$pubCache = $env:PUB_CACHE
if (-not $pubCache) {
    $flutterBin = Get-Command flutter -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source
    if ($flutterBin) {
        $flutterDir = (Get-Item $flutterBin).Directory.Parent.FullName
        $pubCache = Join-Path $flutterDir "bin\cache\pub"
    }
}
if (-not $pubCache -or -not (Test-Path $pubCache)) {
    $pubCache = Join-Path $env:LOCALAPPDATA "Pub\Cache"
}
$hosted = Join-Path $pubCache "hosted\pub.dev"
$pdfxDirs = Get-ChildItem -Path $hosted -Filter "pdfx-*" -Directory -ErrorAction SilentlyContinue
if (-not $pdfxDirs) {
    Write-Host "[patch_pdfx] Run 'flutter pub get' in frontend first. No pdfx package found under $hosted" -ForegroundColor Red
    exit 1
}
$pdfxDir = $pdfxDirs[0].FullName
$cmakePath = Join-Path $pdfxDir "windows\CMakeLists.txt"
if (-not (Test-Path $cmakePath)) {
    Write-Host "[patch_pdfx] $cmakePath not found." -ForegroundColor Red
    exit 1
}

$content = Get-Content -Path $cmakePath -Raw
$markerUrl = "if(NOT DEFINED CACHE{PDFIUM_URL})"
$markerSkip = "Use pre-extracted pdfium from parent"
if ($content -and $content.Contains($markerUrl) -and $content.Contains($markerSkip)) {
    Write-Host "[patch_pdfx] Already patched: $cmakePath" -ForegroundColor Green
    exit 0
}

# 1) Wrap URL block so parent-provided PDFIUM_URL is not overwritten (only if not already wrapped).
$content = Get-Content -Path $cmakePath -Raw
$content = $content -replace "`r`n", "`n"
$needle = "if(`${PDFIUM_VERSION} STREQUAL `"latest`")`n  set(PDFIUM_URL `"https://github.com/bblanchon/pdfium-binaries/releases/latest/download/pdfium-windows-`${ARCH}.zip`")`nelseif(PDFIUM_BINARY_NEW_FORMAT)`n  set(PDFIUM_URL `"https://github.com/bblanchon/pdfium-binaries/releases/download/chromium/`${PDFIUM_VERSION}/pdfium-win-`${ARCH}.tgz`")`nelse()`n  set(PDFIUM_URL `"https://github.com/bblanchon/pdfium-binaries/releases/download/chromium/`${PDFIUM_VERSION}/pdfium-windows-`${ARCH}.zip`")`nendif()"
$replacement = "if(NOT DEFINED CACHE{PDFIUM_URL})`nif(`${PDFIUM_VERSION} STREQUAL `"latest`")`n  set(PDFIUM_URL `"https://github.com/bblanchon/pdfium-binaries/releases/latest/download/pdfium-windows-`${ARCH}.zip`")`nelseif(PDFIUM_BINARY_NEW_FORMAT)`n  set(PDFIUM_URL `"https://github.com/bblanchon/pdfium-binaries/releases/download/chromium/`${PDFIUM_VERSION}/pdfium-win-`${ARCH}.tgz`")`nelse()`n  set(PDFIUM_URL `"https://github.com/bblanchon/pdfium-binaries/releases/download/chromium/`${PDFIUM_VERSION}/pdfium-windows-`${ARCH}.zip`")`nendif()`nendif()"
$newContent = $content
if (-not $content.Contains($markerUrl)) {
    $newContent = $content.Replace($needle, $replacement)
    if ($newContent -eq $content) {
        Write-Host "[patch_pdfx] URL block not found in $cmakePath (plugin version may differ)." -ForegroundColor Red
        exit 1
    }
}

# 2) When parent sets PDFIUM_SOURCE_DIR (pre-extracted pdfium), skip download_project and use it.
$pdfiumSrc = '${PDFIUM_SOURCE_DIR}'
$downloadBlock = "`n# Download pdfium`ninclude(../windows/DownloadProject.cmake)`ndownload_project(`n  PROJ`n  pdfium`n  URL`n  `${PDFIUM_URL}`n  DOWNLOAD_EXTRACT_TIMESTAMP`n  FALSE`n)`n`n# This value is used"
$skipDownloadBlock = "`n# Use pre-extracted pdfium from parent if set, else download`nif(DEFINED CACHE{PDFIUM_SOURCE_DIR} AND EXISTS `"$pdfiumSrc`")`n  set(pdfium_SOURCE_DIR `"$pdfiumSrc`")`n  set(pdfium_BINARY_DIR `"$pdfiumSrc`")`nelse()`n# Download pdfium`ninclude(../windows/DownloadProject.cmake)`ndownload_project(`n  PROJ`n  pdfium`n  URL`n  `${PDFIUM_URL}`n  DOWNLOAD_EXTRACT_TIMESTAMP`n  FALSE`n)`nendif()`n`n# This value is used"
$newContent2 = $newContent.Replace($downloadBlock, $skipDownloadBlock)
if ($newContent2 -eq $newContent) {
    $downloadBlockAlt = "`n# Download pdfium`ninclude(../windows/DownloadProject.cmake)`ndownload_project(`n  PROJ`n  pdfium`n  URL`n  `${PDFIUM_URL}`n  DOWNLOAD_EXTRACT_TIMESTAMP`n  FALSE`n)`n`n# This value"
    $newContent2 = $newContent.Replace($downloadBlockAlt, $skipDownloadBlock)
}
$newContent = $newContent2

Set-Content -Path $cmakePath -Value $newContent -NoNewline
Write-Host "[patch_pdfx] Patched $cmakePath (PDFIUM_URL + PDFIUM_SOURCE_DIR skip-download)" -ForegroundColor Green

# On Windows, Flutter may use a copy instead of a symlink for .plugin_symlinks; patch that copy too.
$ephemeralCmake = Join-Path $FrontendDir "windows\flutter\ephemeral\.plugin_symlinks\pdfx\windows\CMakeLists.txt"
if (Test-Path $ephemeralCmake) {
    $ecContent = Get-Content -Path $ephemeralCmake -Raw
    $ecContent = $ecContent -replace "`r`n", "`n"
    if (-not $ecContent.Contains($markerSkip)) {
        $ecNew = $ecContent
        if (-not $ecContent.Contains($markerUrl)) { $ecNew = $ecContent.Replace($needle, $replacement) }
        $ecNew2 = $ecNew.Replace($downloadBlock, $skipDownloadBlock)
        if ($ecNew2 -ne $ecNew) { $ecNew = $ecNew2 }
        if ($ecNew -ne $ecContent) {
            Set-Content -Path $ephemeralCmake -Value $ecNew -NoNewline
            Write-Host "[patch_pdfx] Patched ephemeral copy $ephemeralCmake" -ForegroundColor Green
        }
    }
}
