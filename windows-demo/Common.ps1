# Shared helpers for this prototype only. Never manage another QEMU process.
$ErrorActionPreference = 'Stop'
$DemoRoot = $PSScriptRoot
$StateFile = Join-Path $DemoRoot 'runtime/vm-state.json'

function Get-ManagedVm {
    if (-not (Test-Path -LiteralPath $StateFile)) { return $null }
    $saved = Get-Content -LiteralPath $StateFile -Raw | ConvertFrom-Json
    $process = Get-Process -Id $saved.pid -ErrorAction SilentlyContinue
    if (-not $process) { return $null }
    $expected = [IO.Path]::GetFullPath((Join-Path $DemoRoot 'runtime/qemu/qemu-system-x86_64.exe'))
    $savedStart = ([datetime]$saved.started).ToUniversalTime()
    if ($process.Path -ne $expected -or $process.StartTime.ToUniversalTime() -ne $savedStart) {
        throw 'The saved PID belongs to another process. This launcher will not control it.'
    }
    return $process
}

function Send-Qmp([string]$Command) {
    $client = New-Object Net.Sockets.TcpClient
    try {
        $client.Connect('127.0.0.1', 18747)
        $stream = $client.GetStream()
        $stream.ReadTimeout = 5000
        $stream.WriteTimeout = 5000
        $reader = New-Object IO.StreamReader($stream)
        $writer = New-Object IO.StreamWriter($stream, (New-Object Text.UTF8Encoding($false)))
        $writer.AutoFlush = $true
        $greeting = $reader.ReadLine() | ConvertFrom-Json
        if (-not $greeting.QMP) { throw 'Unexpected VM control response.' }
        foreach ($operation in @('qmp_capabilities', $Command)) {
            $writer.WriteLine((@{execute=$operation} | ConvertTo-Json -Compress))
            do {
                $line = $reader.ReadLine()
                if ($null -eq $line) { throw 'VM control connection closed.' }
                $reply = $line | ConvertFrom-Json
                if ($reply.error) { throw $reply.error.desc }
            } until ($reply.PSObject.Properties['return'])
        }
        return $reply.return
    } finally { $client.Dispose() }
}
