param([Parameter(Mandatory=$true)][string]$Executable)
# Run with Windows PowerShell 5.1 (the launcher's .NET Framework runtime).
$ErrorActionPreference = 'Stop'
[void][Reflection.Assembly]::LoadFrom([IO.Path]::GetFullPath($Executable))
$testRoot = Join-Path ([IO.Path]::GetTempPath()) ('roleweaver-launcher-test-' + [Guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $testRoot | Out-Null
try {
    $runtime = New-Object RoleWeaverDemo.DemoRuntime $testRoot
    if ($runtime.Settings.SetupComplete -or $runtime.Settings.GamePort -ne 5127) { throw 'Wrong first-run defaults' }
    $runtime.SaveSettings()
    $again = New-Object RoleWeaverDemo.DemoRuntime $testRoot
    if ($again.Settings.Instance -ne $runtime.Settings.Instance) { throw 'Installation identity changed' }
    $again.Settings.GamePort = $again.Settings.DashboardPort
    $rejected = $false
    try { $again.ValidateSettings() } catch { $rejected = $true }
    if (-not $rejected) { throw 'Duplicate ports accepted' }
    if ([RoleWeaverDemo.DemoRuntime]::Quote('path with spaces\') -ne '"path with spaces\\"') { throw 'Trailing slash quoting failed' }
    if ([RoleWeaverDemo.DemoRuntime]::Quote('a"b') -ne '"a\"b"') { throw 'Quote escaping failed' }
    [RoleWeaverDemo.DemoRuntime]::CreateSshIdentity($testRoot)
    $pub = (Get-Content -Raw (Join-Path $testRoot 'admin-key.pub')).Trim()
    $derived = & ssh-keygen.exe -y -f (Join-Path $testRoot 'admin-key')
    if ($LASTEXITCODE -ne 0 -or -not $pub.StartsWith($derived.Trim())) { throw 'Generated RSA key pair does not match' }
    $keyHash = (Get-FileHash (Join-Path $testRoot 'admin-key')).Hash
    [RoleWeaverDemo.DemoRuntime]::CreateSshIdentity($testRoot)
    if ((Get-FileHash (Join-Path $testRoot 'admin-key')).Hash -ne $keyHash) { throw 'Existing key was replaced' }
    $record = @{Pid=$PID;Started=(Get-Process -Id $PID).StartTime.ToUniversalTime().Ticks} | ConvertTo-Json
    [IO.File]::WriteAllText((Join-Path $testRoot 'userdata/vm-state.json'), $record)
    $rejected = $false
    try { $runtime.ManagedProcess() } catch { $rejected = $true }
    if (-not $rejected) { throw 'Launcher accepted a process it does not own' }
    Write-Output 'PASS: defaults, persistent identity, duplicate ports, Windows quoting, RSA identity, key reuse and process ownership.'
} finally {
    $resolved = [IO.Path]::GetFullPath($testRoot)
    $allowed = [IO.Path]::GetFullPath([IO.Path]::GetTempPath())
    if (-not $resolved.StartsWith($allowed, [StringComparison]::OrdinalIgnoreCase) -or -not ([IO.Path]::GetFileName($resolved)).StartsWith('roleweaver-launcher-test-')) { throw 'Unsafe test cleanup path' }
    Remove-Item -LiteralPath $resolved -Recurse -Force
}
