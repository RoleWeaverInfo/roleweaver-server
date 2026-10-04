. (Join-Path $PSScriptRoot 'Common.ps1')
$process = Get-ManagedVm
if (-not $process) { Write-Host 'The demo VM is stopped.'; exit 0 }
$state = Send-Qmp 'query-status'
Write-Host "VM: $($state.status); software emulation (TCG); PID $($process.Id)"
Write-Host ('QEMU working memory: {0:N0} MB' -f ($process.WorkingSet64 / 1MB))
try {
    $response = Invoke-WebRequest -UseBasicParsing -Uri 'http://127.0.0.1:8747/login' -TimeoutSec 5
    Write-Host 'Dashboard is ready: http://127.0.0.1:8747/'
    Write-Host 'Check Health & Support in the dashboard for the game bridge status.'
} catch { Write-Host 'Dashboard is not ready yet. Boot progress is in logs/serial.log.' }
function Test-GameServer {
    # NWN's read-only BNES query returns the server name; it does not log in a player.
    $socket = New-Object Net.Sockets.UdpClient(0)
    try {
        $socket.Client.ReceiveTimeout = 3000
        $localPort = [uint16]$socket.Client.LocalEndPoint.Port
        [byte[]]$packet = [Text.Encoding]::ASCII.GetBytes('BNES') + [BitConverter]::GetBytes($localPort) + [byte]0
        $socket.Send($packet, $packet.Length, '127.0.0.1', 5127) | Out-Null
        $sender = New-Object Net.IPEndPoint([Net.IPAddress]::Any, 0)
        $reply = $socket.Receive([ref]$sender)
        if ($reply.Length -lt 9 -or [Text.Encoding]::ASCII.GetString($reply,0,4) -ne 'BNER') {
            throw 'Unexpected game response.'
        }
        Write-Host 'Game server is answering UDP queries.'
    } catch { Write-Host 'Game server is not answering yet; check Health & Support once the dashboard opens.' }
    finally { $socket.Dispose() }
}
Test-GameServer
Write-Host 'NWN Direct Connect: 127.0.0.1:5127'
