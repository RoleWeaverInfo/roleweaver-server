param([Parameter(Mandatory=$true)][string]$Folder)
# Disposable test copy only. Uses a synthetic key and a loopback-only local model
# endpoint; never sends a request to a hosted LLM or reads real provider secrets.
$ErrorActionPreference = 'Stop'
[void][Reflection.Assembly]::LoadFrom((Join-Path $Folder 'Role Weaver Demo.exe'))
$runtime = New-Object RoleWeaverDemo.DemoRuntime $Folder
$runtime.Login('roleweaver')
$health = $runtime.BridgeState()
if ($health -ne 'healthy') { throw ('Bridge is not ready: ' + $health) }
$initial = $runtime.LlmStatus()
if ($initial['active'] -ne 'offline') { throw 'Test requires a fresh offline installation' }
$runtime.SaveProvider('lmstudio', 'local-test-model', 'test-only-not-a-real-key', 'http://10.0.2.2:18889/v1', $true)
$saved = $runtime.LlmStatus()
if (-not $saved['profiles']['lmstudio']['key_set']) { throw 'Provider key was not saved' }
$runtime.SaveProvider('lmstudio', 'local-test-model-v2', '', 'http://10.0.2.2:18889/v1', $true)
$kept = $runtime.LlmStatus()
if (-not $kept['profiles']['lmstudio']['key_set'] -or $kept['profiles']['lmstudio']['model'] -ne 'local-test-model-v2') { throw 'Provider edit lost the existing key or model' }
$runtime.SaveProvider('offline', '', '', '', $true)
if (-not $runtime.Settings.SetupComplete) { throw 'First-run state was not saved' }
$again = New-Object RoleWeaverDemo.DemoRuntime $Folder
if (-not $again.Settings.SetupComplete -or -not $again.IsRunning()) { throw 'Launcher reconnect failed' }
$process = $again.ManagedProcess()
$before = $process.Id
$process.Dispose()
$again.Start()
$process = $again.ManagedProcess()
if ($process.Id -ne $before) { throw 'A second VM was started' }
$process.Dispose()
$leaks = Get-ChildItem -LiteralPath (Join-Path $Folder 'userdata') -Recurse -File | Where-Object { $_.Extension -ne '.qcow2' } | Select-String -SimpleMatch 'test-only-not-a-real-key'
if ($leaks) { throw 'Synthetic API key leaked into a Windows-side text file' }
Write-Output 'PASS: dashboard authentication, bridge health, provider save/edit, masked key status, setup persistence, existing-VM reuse and no Windows plaintext key.'
