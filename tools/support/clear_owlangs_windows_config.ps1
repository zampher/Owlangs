# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0
#
# Clear Owlangs Windows runtime config so the customer can reconfigure from scratch.
# Called by clear_owlangs_windows_config.bat

param(
    [string]$BackupDir = "",
    [string]$TemplateDir = ""
)

$ErrorActionPreference = "Stop"

function Get-CandidateConfigRoots {
    $roots = New-Object System.Collections.Generic.List[string]
    $add = {
        param([string]$p)
        if ([string]::IsNullOrWhiteSpace($p)) { return }
        $full = [System.IO.Path]::GetFullPath($p)
        if (-not $roots.Contains($full)) { [void]$roots.Add($full) }
    }

    & $add (Join-Path $env:ProgramData "Owlangs\configs")
    & $add (Join-Path $env:ProgramData "Owlangs")
    & $add (Join-Path $env:LOCALAPPDATA "Owlangs\configs")
    if ($env:OWLANGS_CONFIG_PATH) {
        $base = $env:OWLANGS_CONFIG_PATH.TrimEnd("\")
        & $add (Join-Path $base "configs")
        & $add $base
    }
    return $roots
}

function Find-TemplateFile {
    param([string]$FileName)
    $candidates = New-Object System.Collections.Generic.List[string]
    if ($TemplateDir) {
        $candidates.Add((Join-Path $TemplateDir $FileName))
        $candidates.Add((Join-Path $TemplateDir "templates\$FileName"))
    }
    $scriptDir = Split-Path -Parent $PSCommandPath
    $repoConfigs = [System.IO.Path]::GetFullPath((Join-Path $scriptDir "..\..\configs"))
    $candidates.Add((Join-Path $repoConfigs $FileName))

    foreach ($pf in @($env:ProgramFiles, ${env:ProgramFiles(x86)})) {
        if (-not $pf) { continue }
        foreach ($leaf in @(
            "Owlangs\Document Agent\config",
            "Owlangs\config",
            "Owlangs"
        )) {
            $candidates.Add((Join-Path $pf "$leaf\$FileName"))
            $candidates.Add((Join-Path $pf "$leaf\templates\$FileName"))
        }
    }

    # Portable / next to running install: common relative guesses
    foreach ($root in @(
        (Join-Path $env:ProgramData "Owlangs\configs"),
        (Join-Path $env:ProgramData "Owlangs")
    )) {
        $candidates.Add((Join-Path $root $FileName))
    }

    foreach ($c in $candidates) {
        if (Test-Path -LiteralPath $c) { return $c }
    }
    return $null
}

function Write-Utf8NoBom {
    param([string]$Path, [string]$Content)
    $dir = Split-Path -Parent $Path
    if ($dir -and -not (Test-Path -LiteralPath $dir)) {
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
    }
    [System.IO.File]::WriteAllText($Path, $Content, [System.Text.UTF8Encoding]::new($false))
}

function New-EmptySecretsJson {
    return (@{
        _comment = "Sensitive configuration - recreated by clear_owlangs_windows_config"
        _schema_version = 2
        api_keys = @{}
        mineru_token = @{ key = ""; configured = $false }
        mineru_local_token = @{ key = ""; configured = $false }
        docling_auth = @{
            auth_type = "none"
            token = ""
            header_name = ""
            header_value = ""
        }
    } | ConvertTo-Json -Depth 20)
}

# User/runtime files that should be cleared for a fresh reconfigure.
# Keep platforms.json / system.json / local_users.json so login & engine list remain.
$clearNames = @(
    "secrets.json",
    "secrets.json.bak",
    "app_config.json",
    "ai_platform_status.json",
    "local.json",
    "static.json"
)

$touched = 0
$roots = Get-CandidateConfigRoots
$seenFiles = New-Object "System.Collections.Generic.HashSet[string]"

Write-Host "Config roots to scan:"
foreach ($r in $roots) { Write-Host "  - $r" }
Write-Host ""

foreach ($root in $roots) {
    if (-not (Test-Path -LiteralPath $root)) {
        Write-Host "[skip dir] $root"
        continue
    }

    foreach ($name in $clearNames) {
        $path = Join-Path $root $name
        if (-not (Test-Path -LiteralPath $path)) { continue }
        if (-not $seenFiles.Add([System.IO.Path]::GetFullPath($path))) { continue }

        Write-Host "[remove] $path"
        Remove-Item -LiteralPath $path -Force
        $touched++

        # Recreate secrets.json from template (or empty stub) so app can start cleanly.
        if ($name -eq "secrets.json") {
            $tpl = Find-TemplateFile "secrets.json.template"
            if ($tpl) {
                Copy-Item -LiteralPath $tpl -Destination $path -Force
                Write-Host "[create] $path  (from template: $tpl)"
            } else {
                Write-Utf8NoBom -Path $path -Content (New-EmptySecretsJson)
                Write-Host "[create] $path  (empty stub; template not found)"
            }
            $touched++
        }

        if ($name -eq "app_config.json") {
            $tpl = Find-TemplateFile "app_config.json.template"
            if (-not $tpl) { $tpl = Find-TemplateFile "app_config.json" }
            if ($tpl) {
                Copy-Item -LiteralPath $tpl -Destination $path -Force
                Write-Host "[create] $path  (from template: $tpl)"
                $touched++
            } else {
                Write-Host "[info] app_config.json will be recreated on next app start"
            }
        }
    }
}

if ($touched -eq 0) {
    Write-Host "WARNING: No runtime config files were found to clear." -ForegroundColor Red
    Write-Host "If this is a portable/custom install, set OWLANGS_CONFIG_PATH and rerun." -ForegroundColor Red
    if ($BackupDir) { Write-Host "Backup folder: $BackupDir" -ForegroundColor Red }
    exit 2
}

Write-Host ""
Write-Host "Done. Cleared/recreated entries: $touched"
Write-Host "Kept: platforms.json / system.json / local_users.json (if present)"
if ($BackupDir) { Write-Host "Backup folder: $BackupDir" }
exit 0
