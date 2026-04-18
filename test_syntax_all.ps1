$files = @(
    'backend/config_manager.py',
    'tools/build/build_win_singlefile.ps1'
)

$allOk = $true
foreach ($file in $files) {
    if (Test-Path $file) {
        $content = Get-Content $file -Raw
        $errors = $null
        [void][System.Management.Automation.PSParser]::Tokenize($content, [ref]$errors)
        
        if ($errors.Count -gt 0) {
            Write-Host "$file : FAILED" -ForegroundColor Red
            $errors | ForEach-Object { Write-Host "  Line $($_.Token.StartLine): $($_.Message)" }
            $allOk = $false
        } else {
            Write-Host "$file : OK" -ForegroundColor Green
        }
    } else {
        Write-Host "$file : NOT FOUND" -ForegroundColor Yellow
    }
}

# Python syntax check
if (Test-Path 'backend/config_manager.py') {
    $result = python -m py_compile backend/config_manager.py 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "backend/config_manager.py (Python) : OK" -ForegroundColor Green
    } else {
        Write-Host "backend/config_manager.py (Python) : FAILED" -ForegroundColor Red
        Write-Host $result
        $allOk = $false
    }
}

if ($allOk) { exit 0 } else { exit 1 }
