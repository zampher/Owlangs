# Search for version number references in frontend, backend, launcher, and configs.
# Usage:
#   .\tools\search_version_refs.ps1           # search for 1.0.0.0 and common version patterns
#   .\tools\search_version_refs.ps1 -Strict  # only literal 1.0.0.0
#
# Output: file path and line number for each match; summary by category.

param(
    [switch]$Strict   # only search literal "1.0.0.0"
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RootDir = Split-Path -Parent (Split-Path -Parent $ScriptDir)
Set-Location $RootDir

$searchDirs = @("backend", "frontend\lib", "frontend\windows", "launcher", "configs", "tools")
$excludeDirs = @("node_modules", "build", ".dart_tool", "dist", "obj", "bin", "__pycache__", "\.venv")
$extensions = @("*.py", "*.dart", "*.cs", "*.csproj", "*.json", "*.yaml", "*.iss", "*.nsi")

# Literal version strings (X.Y.Z.W or X.Y.Z)
$literalPattern = "1\.0\.0\.0|2\.0\.0\.0|2\.0\.0|1\.0\.0"
# Version key patterns (assignment or JSON key)
$keyPatterns = @(
    "__version__\s*=",
    "appVersion\s*=",
    '"version"\s*:',
    "'version'\s*:",
    "<Version>",
    "DisplayVersion",
    "MyAppVersion",
    "version:"
)

function Get-SearchPattern {
    if ($Strict) {
        return [regex]::Escape("1.0.0.0")
    }
    # Combined: literal versions or version key lines (so we see both)
    return "(?:$literalPattern|__version__|appVersion|[\`"']version[\`"']\s*:|<Version>|DisplayVersion|MyAppVersion)"
}

$pattern = Get-SearchPattern
$results = [System.Collections.ArrayList]::new()

foreach ($dir in $searchDirs) {
    if (-not (Test-Path $dir)) { continue }
    $files = Get-ChildItem -Path $dir -Recurse -File -ErrorAction SilentlyContinue | Where-Object {
        $p = $_.FullName
        $excluded = $false
        foreach ($e in $excludeDirs) {
            if ($p -match $e) { $excluded = $true; break }
        }
        -not $excluded -and ($_.Extension -match '\.(py|dart|cs|csproj|json|yaml|iss|nsi)$')
    }
    foreach ($f in $files) {
        $relPath = $f.FullName.Replace($RootDir + [IO.Path]::DirectorySeparatorChar, "").Replace("\", "/")
        $lineNum = 0
        Get-Content -Path $f.FullName -Encoding UTF8 -ErrorAction SilentlyContinue | ForEach-Object {
            $lineNum++
            $line = $_
            if ($line -match $pattern) {
                $category = switch -Regex ($relPath) {
                    "^backend" { "backend" }
                    "^frontend" { "frontend" }
                    "^launcher" { "launcher" }
                    "^configs" { "configs" }
                    "^tools" { "tools" }
                    default { "other" }
                }
                [void]$results.Add([PSCustomObject]@{
                    Category = $category
                    File = $relPath
                    Line = $lineNum
                    Content = (& { $t = $line.Trim(); if ($t.Length -gt 100) { $t.Substring(0, 100) + "..." } else { $t } })
                })
            }
        }
    }
}

# Group by file and output
Write-Host "=== Version references (pattern: $pattern) ===" -ForegroundColor Cyan
Write-Host ""

$byFile = $results | Group-Object -Property File | Sort-Object Name
$byCategory = $results | Group-Object -Property Category

foreach ($cat in @("backend", "frontend", "launcher", "configs", "tools", "other")) {
    $items = $byCategory | Where-Object { $_.Name -eq $cat }
    if (-not $items -or $items.Count -eq 0) { continue }
    $entries = $items[0].Group
    Write-Host "--- $cat ---" -ForegroundColor Yellow
    foreach ($e in ($entries | Sort-Object File, Line)) {
        Write-Host "  $($e.File):$($e.Line)" -ForegroundColor White
        Write-Host "    $($e.Content)" -ForegroundColor Gray
    }
    Write-Host ""
}

Write-Host "=== Summary ===" -ForegroundColor Cyan
Write-Host "Total matches: $($results.Count)" -ForegroundColor White
Write-Host "Files with version refs: $($byFile.Count)" -ForegroundColor White
Write-Host ""
Write-Host "Single source of truth: backend/__init__.py (__version__)" -ForegroundColor Green
Write-Host "Sync script: .\tools\setup\sync_version.ps1 (writes to configs, frontend, launcher, tools)" -ForegroundColor Green
Write-Host "See: docs/VERSION_MANAGEMENT.md" -ForegroundColor Gray
