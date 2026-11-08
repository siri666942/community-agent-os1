param([switch]$LocalOnly)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$stateDir = Join-Path $PSScriptRoot '.dbmcp'
New-Item -ItemType Directory -Force -Path $stateDir | Out-Null
$pidFile = Join-Path $stateDir 'opsie-server.pid'
if (Test-Path -LiteralPath $pidFile) {
    $previousId = 0
    if ([int]::TryParse((Get-Content -LiteralPath $pidFile -Raw).Trim(), [ref]$previousId)) {
        $previous = Get-CimInstance Win32_Process -Filter "ProcessId=$previousId" -ErrorAction SilentlyContinue
        if ($previous -and $previous.CommandLine -match 'opsie\.api') {
            Write-Host "Opsie is already running. Local address: http://127.0.0.1:8780/"
            exit 0
        }
    }
}
$python = Join-Path $PSScriptRoot '.opsie-venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) {
    if (Get-Command uv -ErrorAction SilentlyContinue) {
        & uv venv '.opsie-venv' --python 3.13
        if ($LASTEXITCODE -ne 0) { throw 'Failed to create the Python environment.' }
        & uv pip install --python $python -r requirements.txt
    } else {
        & python -m venv '.opsie-venv'
        if ($LASTEXITCODE -ne 0) { throw 'Failed to create the Python environment.' }
        & $python -m pip install -r requirements.txt
    }
    if ($LASTEXITCODE -ne 0) { throw 'Failed to install Python dependencies.' }
}
& $python -m opsie.setup_demo
if ($LASTEXITCODE -ne 0) { throw 'Demo initialization failed. Check local database configuration.' }
$env:OPSIE_HOST = if ($LocalOnly) { '127.0.0.1' } else { '0.0.0.0' }
$env:OPSIE_PORT = '8780'
$process = Start-Process -FilePath $python -ArgumentList @('-m','opsie.api') -WorkingDirectory $PSScriptRoot `
    -WindowStyle Hidden -RedirectStandardOutput (Join-Path $stateDir 'opsie-server.out') `
    -RedirectStandardError (Join-Path $stateDir 'opsie-server.err') -PassThru
$process.Id | Set-Content -LiteralPath $pidFile -Encoding ascii
$ready = $false
for ($attempt = 0; $attempt -lt 20; $attempt++) {
    try {
        $answer = Invoke-RestMethod -Uri 'http://127.0.0.1:8780/health' -TimeoutSec 5
        if ($answer.ok -and $answer.service -eq 'opsie') { $ready = $true; break }
    } catch { Start-Sleep -Milliseconds 500 }
}
if (-not $ready) { throw 'Opsie did not start. Check .dbmcp/opsie-server.err.' }
Write-Host 'Opsie is running: http://127.0.0.1:8780/'
if (-not $LocalOnly) {
    Get-NetIPAddress -AddressFamily IPv4 -AddressState Preferred -ErrorAction SilentlyContinue |
        Where-Object { $_.IPAddress -notlike '127.*' -and $_.IPAddress -notlike '169.254.*' } |
        ForEach-Object { Write-Host ("LAN: http://{0}:8780/" -f $_.IPAddress) }
}
Write-Host 'Demo account credentials: .dbmcp/demo-accounts.json'
