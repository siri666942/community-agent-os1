$ErrorActionPreference = 'Stop'
$pidFile = Join-Path $PSScriptRoot '.dbmcp\opsie-server.pid'
if (-not (Test-Path -LiteralPath $pidFile)) { Write-Host 'No recorded Opsie server.'; exit 0 }
$processIdValue = 0
if (-not [int]::TryParse((Get-Content -LiteralPath $pidFile -Raw).Trim(), [ref]$processIdValue)) { throw 'Invalid server PID file.' }
$process = Get-CimInstance Win32_Process -Filter "ProcessId=$processIdValue" -ErrorAction SilentlyContinue
if ($process -and $process.CommandLine -match 'opsie\.api') {
    Stop-Process -Id $processIdValue
    Write-Host 'Opsie server stopped.'
} else { Write-Host 'Recorded Opsie server is not running.' }
Remove-Item -LiteralPath $pidFile
