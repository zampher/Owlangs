# Download and vendor pdfjs-dist into frontend/web/pdfjs for offline PDF preview.
# Version must stay aligned with pdfx (see pdfx bin/install_web.dart).
param(
    [string]$Version = "4.6.82",
    [string]$MirrorBase = "https://registry.npmmirror.com/pdfjs-dist/-"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Dest = Join-Path $Root "frontend\web\pdfjs"
$TmpTgz = Join-Path $env:TEMP "pdfjs-dist-$Version.tgz"
$Extract = Join-Path $env:TEMP "pdfjs-dist-extract-$Version"
$Url = "$MirrorBase/pdfjs-dist-$Version.tgz"

Write-Host "Downloading $Url"
Invoke-WebRequest -Uri $Url -OutFile $TmpTgz -UseBasicParsing -TimeoutSec 180

if (Test-Path $Extract) { Remove-Item $Extract -Recurse -Force }
New-Item -ItemType Directory -Force -Path $Extract | Out-Null
tar -xzf $TmpTgz -C $Extract
$Pkg = Join-Path $Extract "package"

if (Test-Path $Dest) { Remove-Item $Dest -Recurse -Force }
New-Item -ItemType Directory -Force -Path (Join-Path $Dest "build") | Out-Null
Copy-Item (Join-Path $Pkg "build\pdf.min.mjs") (Join-Path $Dest "build\") -Force
Copy-Item (Join-Path $Pkg "build\pdf.worker.min.mjs") (Join-Path $Dest "build\") -Force
Copy-Item (Join-Path $Pkg "cmaps") (Join-Path $Dest "cmaps") -Recurse -Force
Copy-Item (Join-Path $Pkg "standard_fonts") (Join-Path $Dest "standard_fonts") -Recurse -Force
Copy-Item (Join-Path $Pkg "LICENSE") (Join-Path $Dest "LICENSE") -Force

Write-Host "Vendored pdfjs-dist@$Version into $Dest"
Write-Host "Remember: frontend/web/index.html must reference pdfjs/ paths (no CDN)."
