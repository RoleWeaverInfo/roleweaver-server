param([Parameter(Mandatory=$true)][string]$OutputDirectory)
$ErrorActionPreference = 'Stop'
$repo = Split-Path $PSScriptRoot
$output = [IO.Path]::GetFullPath($OutputDirectory)
New-Item -ItemType Directory -Force -Path $output | Out-Null
$compiler = Join-Path $env:WINDIR 'Microsoft.NET/Framework64/v4.0.30319/csc.exe'
$target = Join-Path $output 'LauncherFlowTests.exe'
$report = Join-Path $output 'model-flow-result.txt'
$splash = Join-Path $repo 'roleweaver/static/rw_server_splash.png'
& $compiler /nologo /target:winexe /platform:x64 /main:RoleWeaverDemo.LauncherFlowTests "/out:$target" /reference:System.Windows.Forms.dll /reference:System.Drawing.dll /reference:System.Web.Extensions.dll "/resource:$splash,RoleWeaver.Splash" (Join-Path $PSScriptRoot 'launcher/DemoRuntime.cs') (Join-Path $PSScriptRoot 'launcher/Program.cs') (Join-Path $PSScriptRoot 'tests/LauncherFlowTests.cs')
if ($LASTEXITCODE -ne 0) { throw 'Test compilation failed' }
$process = Start-Process -FilePath $target -ArgumentList ('"' + $report + '"') -PassThru -WindowStyle Hidden
if (-not $process.WaitForExit(30000)) { $process.Kill(); throw 'UI regression test timed out' }
Get-Content -LiteralPath $report
if ($process.ExitCode -ne 0) { throw 'Model loading regression test failed' }
