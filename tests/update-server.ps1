$ErrorActionPreference = 'Stop'

$server = 'shared-server'
$remoteTemp = '/tmp/opc-update.sh'
$serverUpdater = '/usr/local/sbin/opc-update'
$bashScript = Join-Path $PSScriptRoot 'update-server.sh'

if (-not (Test-Path -LiteralPath $bashScript)) {
    throw "Missing server updater: $bashScript"
}

Write-Host "Uploading updater to $server..."
& scp $bashScript "${server}:$remoteTemp"
if ($LASTEXITCODE -ne 0) {
    throw "Could not upload the server updater (exit code $LASTEXITCODE)."
}

Write-Host "Updating the website on $server..."
& ssh -T $server "install -o root -g root -m 755 $remoteTemp $serverUpdater && $serverUpdater"
if ($LASTEXITCODE -ne 0) {
    throw "Server deployment failed (exit code $LASTEXITCODE)."
}

Write-Host 'Deployment completed.'
