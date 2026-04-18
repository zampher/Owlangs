# Create Owlangs shortcut with environment variables
param(
    [string]$TargetPath,
    [string]$ShortcutPath,
    [string]$WorkingDirectory,
    [string]$Description,
    [string]$IconPath = ""
)

# Create WScript.Shell object
$WshShell = New-Object -comObject WScript.Shell

# Create shortcut
$Shortcut = $WshShell.CreateShortcut($ShortcutPath)
$Shortcut.TargetPath = $TargetPath
$Shortcut.WorkingDirectory = $WorkingDirectory
$Shortcut.Description = $Description

if ($IconPath -and (Test-Path $IconPath)) {
    $Shortcut.IconLocation = "$IconPath,0"
}

$Shortcut.Save()

Write-Host "Created shortcut: $ShortcutPath"
Write-Host "Target: $TargetPath"
Write-Host "Working Directory: $WorkingDirectory"
if ($IconPath) {
    Write-Host "Icon: $IconPath"
}
