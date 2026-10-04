param()
. (Join-Path $PSScriptRoot 'Common.ps1')
$running = Get-ManagedVm
if ($running) {
    Write-Host "Demo VM is already running (PID $($running.Id))."
    Write-Host 'Dashboard: http://127.0.0.1:8747/  Game: 127.0.0.1:5127'
    exit 0
}
foreach ($name in @('runtime/qemu/qemu-system-x86_64.exe','runtime/demo.qcow2','runtime/seed.iso','runtime/vmlinuz')) {
    if (-not (Test-Path -LiteralPath (Join-Path $DemoRoot $name))) { throw "Missing prototype file: $name" }
}
foreach ($port in @(8747,12222,18747)) {
    $listener = New-Object Net.Sockets.TcpListener([Net.IPAddress]::Loopback, $port)
    try { $listener.Start() } catch { throw "TCP port $port is in use. Close the conflicting program first." }
    finally { $listener.Stop() }
}
$udp = New-Object Net.Sockets.UdpClient
try {
    $udp.ExclusiveAddressUse = $true
    $udp.Client.Bind((New-Object Net.IPEndPoint([Net.IPAddress]::Loopback, 5127)))
} catch { throw 'Game UDP port 5127 is already in use.' }
finally { $udp.Dispose() }
New-Item -ItemType Directory -Force -Path (Join-Path $DemoRoot 'logs') | Out-Null
if (Test-Path -LiteralPath (Join-Path $DemoRoot 'logs/serial.log')) {
    Copy-Item -LiteralPath (Join-Path $DemoRoot 'logs/serial.log') -Destination (Join-Path $DemoRoot ('logs/serial-' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '.log'))
}
# Explicit TCG: this proof of concept never silently falls back to WHPX/Hyper-V.
# All argument paths are relative to WorkingDirectory so folders with spaces work.
$arguments = @(
    '-name','roleweaver-qemu-demo',
    '-L','runtime/qemu/share',
    '-machine','q35,hpet=off','-accel','tcg,thread=multi','-cpu','max','-smp','2','-m','2048',
    '-kernel','runtime/vmlinuz','-append','"root=/dev/vda1 rw console=ttyS0 noapic"',
    '-drive','file=runtime/demo.qcow2,if=virtio,format=qcow2',
    '-drive','file=runtime/seed.iso,if=virtio,format=raw,readonly=on',
    '-device','virtio-rng-pci',
    '-nic','user,model=virtio-net-pci,hostfwd=tcp:127.0.0.1:12222-:22,hostfwd=tcp:127.0.0.1:8747-:8748,hostfwd=udp:127.0.0.1:5127-:5127',
    '-qmp','tcp:127.0.0.1:18747,server=on,wait=off',
    '-display','none','-monitor','none','-serial','file:logs/serial.log'
)
$process = Start-Process -FilePath (Join-Path $DemoRoot 'runtime/qemu/qemu-system-x86_64.exe') -ArgumentList $arguments -WorkingDirectory $DemoRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $DemoRoot 'logs/qemu-output.log') -RedirectStandardError (Join-Path $DemoRoot 'logs/qemu-error.log')
Start-Sleep -Milliseconds 500
if ($process.HasExited) {
    Get-Content -LiteralPath (Join-Path $DemoRoot 'logs/qemu-error.log')
    throw 'QEMU exited during startup.'
}
$state = @{pid=$process.Id; started=$process.StartTime.ToUniversalTime().ToString('o'); accelerator='tcg'; launched=(Get-Date).ToUniversalTime().ToString('o')}
[IO.File]::WriteAllText($StateFile, ($state | ConvertTo-Json), (New-Object Text.UTF8Encoding($false)))
Write-Host 'Starting the demo using software emulation. Linux and the game may take a few minutes to load.'
Write-Host 'Use Check Status.cmd to check readiness.'
Write-Host 'Dashboard: http://127.0.0.1:8747/  Password: roleweaver (unless changed)'
Write-Host 'NWN:EE Direct Connect: 127.0.0.1:5127'
Write-Host 'For a DM connection use the DM client and password roleweaver.'
Write-Host 'Use Stop Demo.cmd for a clean shutdown.'
