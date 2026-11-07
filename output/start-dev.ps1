# One-click dev launcher for Windows PowerShell 5.1+.
# Starts two separate terminal windows. Close those windows to stop the servers.
[CmdletBinding()]
param(
    [switch]$SkipInstall,
    [switch]$NoBrowser,
    [switch]$UpdateOnly
)

$ErrorActionPreference = 'Stop'
$Branch = 'design/warm-editorial-opc'
$RepoRoot = $PSScriptRoot
$JunctionDir = Join-Path $RepoRoot 'junction'
$WebDir = Join-Path $JunctionDir 'web'

function Assert-ExitCode([string]$Step) {
    if ($LASTEXITCODE -ne 0) {
        throw "$Step failed (exit code $LASTEXITCODE)."
    }
}

function Test-LocalPort([int]$Port) {
    $client = New-Object System.Net.Sockets.TcpClient
    try {
        $pending = $client.BeginConnect('127.0.0.1', $Port, $null, $null)
        if (-not $pending.AsyncWaitHandle.WaitOne(250)) { return $false }
        $client.EndConnect($pending)
        return $true
    }
    catch {
        return $false
    }
    finally {
        $client.Close()
    }
}

function Wait-LocalPort([int]$Port, [System.Diagnostics.Process]$Process) {
    for ($attempt = 0; $attempt -lt 80; $attempt++) {
        if (Test-LocalPort $Port) { return }
        if ($Process.HasExited) {
            throw "Process exited before port $Port was ready. Check the terminal window."
        }
        Start-Sleep -Milliseconds 250
    }
    throw "Port $Port did not become ready. Check the terminal window for errors."
}

function Launch-Server([string]$Title, [string]$Directory, [string]$Command) {
    $safeTitle = $Title.Replace("'", "''")
    $safeDir = $Directory.Replace("'", "''")
    $source = '$Host.UI.RawUI.WindowTitle = ''' + $safeTitle + '''; ' +
              'Set-Location -LiteralPath ''' + $safeDir + '''; ' + $Command
    $encoded = [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($source))
    return Start-Process -FilePath 'powershell.exe' -ArgumentList @(
        '-NoLogo', '-NoExit', '-ExecutionPolicy', 'Bypass', '-EncodedCommand', $encoded
    ) -WorkingDirectory $Directory -PassThru
}

function Resolve-Python {
    $python = Get-Command python.exe -ErrorAction SilentlyContinue
    if ($python) { return @{ Exe = $python.Source; Prefix = @() } }
    $launcher = Get-Command py.exe -ErrorAction SilentlyContinue
    if ($launcher) { return @{ Exe = $launcher.Source; Prefix = @('-3') } }
    throw 'Python 3 was not found. Install Python and add it to PATH.'
}

function Verify-ExistingServer([int]$Port, [string]$Url, [string]$Marker) {
    try {
        $result = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 5
        if ($result.StatusCode -ne 200 -or $result.Content -notmatch [regex]::Escape($Marker)) {
            throw 'Unexpected response'
        }
    }
    catch {
        throw "Port $Port is already occupied by an unknown or unhealthy service. Close it and retry."
    }
}

if (-not (Test-Path -LiteralPath (Join-Path $WebDir 'package.json'))) {
    throw 'Cannot locate junction/web. Run start-dev.cmd from the repository root.'
}
if (-not (Get-Command git.exe -ErrorAction SilentlyContinue)) {
    throw 'Git for Windows is required. Add git.exe to PATH.'
}

Write-Host '[1/4] Updating Git branch...' -ForegroundColor Cyan
& git -C $RepoRoot rev-parse --is-inside-work-tree | Out-Null
Assert-ExitCode 'Git repository check'

# Never overwrite the user's tracked local edits or staged changes.
& git -C $RepoRoot diff --quiet
if ($LASTEXITCODE -ne 0) { throw 'Uncommitted tracked files found. Commit or stash them before launching.' }
& git -C $RepoRoot diff --cached --quiet
if ($LASTEXITCODE -ne 0) { throw 'Staged changes found. Commit or stash them before launching.' }

$fetchRefspec = "refs/heads/${Branch}:refs/remotes/origin/${Branch}"
& git -C $RepoRoot fetch origin $fetchRefspec
Assert-ExitCode 'Git fetch'
$current = (& git -C $RepoRoot branch --show-current).Trim()
if ($current -ne $Branch) {
    & git -C $RepoRoot show-ref --verify --quiet "refs/heads/$Branch"
    if ($LASTEXITCODE -eq 0) {
        & git -C $RepoRoot switch $Branch
    }
    else {
        & git -C $RepoRoot switch --track -c $Branch "origin/$Branch"
    }
    Assert-ExitCode 'Git switch'
}
& git -C $RepoRoot merge --ff-only "origin/$Branch"
Assert-ExitCode 'Git fast-forward'
Write-Host "Checked out and updated: $Branch" -ForegroundColor Green
if ($UpdateOnly) {
    Write-Host "Git update verified; exiting without launching services." -ForegroundColor Green
    return
}

$python = Resolve-Python
$npm = Get-Command npm.cmd -ErrorAction SilentlyContinue
if (-not $npm) { throw 'Node.js / npm was not found. Install Node.js 20.19+ or 22.12+ and retry.' }
$npmExe = $npm.Source

if (-not $SkipInstall) {
    Write-Host '[2/4] Installing Python dependencies...' -ForegroundColor Cyan
    $pythonExe = [string]$python.Exe
    $pipArgs = @($python.Prefix) + @('-m', 'pip', 'install', '-r', (Join-Path $JunctionDir 'requirements.txt'))
    & $pythonExe @pipArgs
    Assert-ExitCode 'Python dependency installation'

    Write-Host '[3/4] Installing React dependencies...' -ForegroundColor Cyan
    Push-Location -LiteralPath $WebDir
    try {
        & $npmExe install --no-audit --no-fund
        Assert-ExitCode 'npm install'
    }
    finally {
        Pop-Location
    }
}
else {
    Write-Host '[2-3/4] Dependency installation skipped.' -ForegroundColor Yellow
}

Write-Host '[4/4] Starting API and Vite in separate terminals...' -ForegroundColor Cyan
if (Test-LocalPort 8765) {
    Verify-ExistingServer 8765 'http://127.0.0.1:8765/api/state' '"tickets"'
    Write-Host 'Backend already running on port 8765; reusing it.' -ForegroundColor Yellow
}
else {
    $escapedPython = $python.Exe.Replace("'", "''")
    $prefixText = ($python.Prefix -join ' ')
    $backendCommand = "& '$escapedPython' $prefixText -m web_api.main"
    $apiProcess = Launch-Server 'OPC - Python API :8765' $JunctionDir $backendCommand
    Wait-LocalPort 8765 $apiProcess
    Write-Host 'Backend ready: http://127.0.0.1:8765' -ForegroundColor Green
}

if (Test-LocalPort 5173) {
    Verify-ExistingServer 5173 'http://127.0.0.1:5173/' '/src/main.jsx'
    Write-Host 'React/Vite already running on port 5173; reusing it.' -ForegroundColor Yellow
}
else {
    $escapedNpm = $npmExe.Replace("'", "''")
    $frontendCommand = "& '$escapedNpm' run dev"
    $webProcess = Launch-Server 'OPC - React Vite :5173' $WebDir $frontendCommand
    Wait-LocalPort 5173 $webProcess
    Write-Host 'Frontend ready: http://127.0.0.1:5173' -ForegroundColor Green
}

$address = 'http://127.0.0.1:5173/#dashboard'
Write-Host ''
Write-Host "Ready! Open: $address" -ForegroundColor Green
Write-Host 'Close the two server terminal windows to stop the apps.'
if (-not $NoBrowser) {
    Start-Process $address
}
