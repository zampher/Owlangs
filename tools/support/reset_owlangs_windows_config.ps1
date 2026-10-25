# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0
#
# Reset Owlangs Windows runtime config (PaddleOCR keys or all API keys).
# Called by reset_owlangs_windows_config.bat

param(
    [ValidateSet("paddle", "full")]
    [string]$Mode = "paddle",
    [string]$BackupDir = ""
)

$ErrorActionPreference = "Stop"

function Convert-ToHashtable {
    # Allow null JSON values (e.g. "token": null) without Mandatory binding errors.
    param([AllowNull()][Parameter(Mandatory = $false)]$InputObject)
    if ($null -eq $InputObject) { return $null }
    if ($InputObject -is [hashtable]) { return $InputObject }
    if ($InputObject -is [System.Collections.IDictionary]) {
        $ht = @{}
        foreach ($key in $InputObject.Keys) {
            $ht[[string]$key] = Convert-ToHashtable -InputObject $InputObject[$key]
        }
        return $ht
    }
    if ($InputObject -is [pscustomobject]) {
        $ht = @{}
        foreach ($prop in $InputObject.PSObject.Properties) {
            $ht[$prop.Name] = Convert-ToHashtable -InputObject $prop.Value
        }
        return $ht
    }
    if ($InputObject -is [System.Collections.IEnumerable] -and -not ($InputObject -is [string])) {
        $list = @()
        foreach ($item in $InputObject) {
            $list += ,(Convert-ToHashtable -InputObject $item)
        }
        return $list
    }
    return $InputObject
}

function Clear-PaddleKeysInMap {
    param([hashtable]$Map)
    if (-not $Map) { return $false }
    $changed = $false
    foreach ($k in @("paddle", "paddle_local")) {
        if ($Map.ContainsKey($k)) {
            $Map[$k] = @{ key = ""; configured = $false }
            $changed = $true
        }
    }
    return $changed
}

function Clear-AllApiKeysInSecrets {
    param([hashtable]$Obj)
    foreach ($section in @("api_keys", "platform_api_keys")) {
        if ($Obj.ContainsKey($section) -and $Obj[$section] -is [hashtable]) {
            $keys = @($Obj[$section].Keys)
            foreach ($k in $keys) {
                $Obj[$section][$k] = @{ key = ""; configured = $false }
            }
        }
    }
    foreach ($tk in @("mineru_token", "translator_mineru_token", "mineru_local_token")) {
        if ($Obj.ContainsKey($tk)) {
            $Obj[$tk] = @{ key = ""; configured = $false }
        }
    }
}

function Write-JsonFile {
    param(
        [string]$Path,
        [hashtable]$Object
    )
    $json = $Object | ConvertTo-Json -Depth 40
    [System.IO.File]::WriteAllText($Path, $json, [System.Text.UTF8Encoding]::new($false))
}

$secretPaths = @(
    (Join-Path $env:ProgramData "Owlangs\secrets.json"),
    (Join-Path $env:ProgramData "Owlangs\configs\secrets.json"),
    (Join-Path $env:LOCALAPPDATA "Owlangs\configs\secrets.json")
)

$appConfigPaths = @(
    (Join-Path $env:ProgramData "Owlangs\app_config.json"),
    (Join-Path $env:ProgramData "Owlangs\configs\app_config.json"),
    (Join-Path $env:LOCALAPPDATA "Owlangs\configs\app_config.json")
)

$statusPaths = @(
    (Join-Path $env:ProgramData "Owlangs\ai_platform_status.json"),
    (Join-Path $env:ProgramData "Owlangs\configs\ai_platform_status.json")
)

# Optional: OWLANGS_CONFIG_PATH override (custom / portable installs)
if ($env:OWLANGS_CONFIG_PATH) {
    $root = $env:OWLANGS_CONFIG_PATH.TrimEnd("\")
    $secretPaths += @(
        (Join-Path $root "secrets.json"),
        (Join-Path $root "configs\secrets.json")
    )
    $appConfigPaths += @(
        (Join-Path $root "app_config.json"),
        (Join-Path $root "configs\app_config.json")
    )
    $statusPaths += @(
        (Join-Path $root "ai_platform_status.json"),
        (Join-Path $root "configs\ai_platform_status.json")
    )
}

$touched = 0

foreach ($p in ($secretPaths | Select-Object -Unique)) {
    if (-not (Test-Path -LiteralPath $p)) {
        Write-Host "[skip] $p"
        continue
    }
    Write-Host "[edit] $p"
    $raw = Get-Content -LiteralPath $p -Raw -Encoding UTF8
    if ([string]::IsNullOrWhiteSpace($raw)) {
        Write-Host "[skip empty] $p"
        continue
    }
    $obj = Convert-ToHashtable -InputObject ($raw | ConvertFrom-Json)
    if ($null -eq $obj) {
        Write-Host "[skip null json] $p"
        continue
    }
    if ($Mode -eq "full") {
        Clear-AllApiKeysInSecrets $obj
    } else {
        foreach ($section in @("api_keys", "platform_api_keys")) {
            if ($obj.ContainsKey($section) -and $obj[$section] -is [hashtable]) {
                [void](Clear-PaddleKeysInMap $obj[$section])
            }
        }
    }
    Write-JsonFile -Path $p -Object $obj
    $touched++
}

foreach ($p in ($appConfigPaths | Select-Object -Unique)) {
    if (-not (Test-Path -LiteralPath $p)) { continue }
    Write-Host "[edit] $p"
    $raw = Get-Content -LiteralPath $p -Raw -Encoding UTF8
    if ([string]::IsNullOrWhiteSpace($raw)) {
        Write-Host "[skip empty] $p"
        continue
    }
    $obj = Convert-ToHashtable -InputObject ($raw | ConvertFrom-Json)
    if ($null -eq $obj) {
        Write-Host "[skip null json] $p"
        continue
    }
    foreach ($section in @("platform_api_keys", "glossary_platform_api_keys")) {
        if ($obj.ContainsKey($section) -and $obj[$section] -is [hashtable]) {
            if ($Mode -eq "full") {
                $keys = @($obj[$section].Keys)
                foreach ($k in $keys) { $obj[$section][$k] = "" }
            } else {
                foreach ($k in @("paddle", "paddle_local")) {
                    if ($obj[$section].ContainsKey($k)) { $obj[$section][$k] = "" }
                }
            }
        }
    }
    Write-JsonFile -Path $p -Object $obj
    $touched++
}

foreach ($p in ($statusPaths | Select-Object -Unique)) {
    if (Test-Path -LiteralPath $p) {
        Remove-Item -LiteralPath $p -Force
        Write-Host "[delete] $p"
        $touched++
    }
}

if ($touched -eq 0) {
    Write-Host "WARNING: No Owlangs config files were found." -ForegroundColor Red
    Write-Host "If this is a portable/custom install, set OWLANGS_CONFIG_PATH then rerun." -ForegroundColor Red
    if ($BackupDir) { Write-Host "Backup folder: $BackupDir" -ForegroundColor Red }
    exit 2
}

Write-Host "Done. Updated/deleted entries: $touched"
if ($BackupDir) { Write-Host "Backup folder: $BackupDir" }
exit 0
