. (Join-Path $PSScriptRoot 'Common.ps1')
$process = Get-ManagedVm
if (-not $process) { Write-Host 'The demo VM is stopped.'; exit 0 }
Send-Qmp 'system_powerdown' | Out-Null
Write-Host 'Saving and shutting down the demo VM...'
if ($process.WaitForExit(60000)) {
    Remove-Item -LiteralPath $StateFile -ErrorAction SilentlyContinue
    Write-Host 'Demo stopped.'
} else {
    Write-Host 'Shutdown is still in progress. Wait, then check status. The launcher has not forced a power cut.'
}
