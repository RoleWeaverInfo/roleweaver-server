param([Parameter(Mandatory=$true)][string]$OutputDirectory)
$ErrorActionPreference = 'Stop'
$repo = Split-Path $PSScriptRoot
$output = [IO.Path]::GetFullPath($OutputDirectory)
New-Item -ItemType Directory -Force -Path $output | Out-Null
$compiler = Join-Path $env:WINDIR 'Microsoft.NET\Framework64\v4.0.30319\csc.exe'
$splash = Join-Path $repo 'roleweaver\static\rw_server_splash.png'
$target = Join-Path $output 'Role Weaver Demo.exe'
& $compiler /nologo /target:winexe /platform:x64 /optimize+ "/out:$target" /reference:System.Windows.Forms.dll /reference:System.Drawing.dll /reference:System.Web.Extensions.dll "/resource:$splash,RoleWeaver.Splash" (Join-Path $PSScriptRoot 'launcher\DemoRuntime.cs') (Join-Path $PSScriptRoot 'launcher\Program.cs')
if ($LASTEXITCODE -ne 0) { throw 'Launcher compilation failed.' }
Write-Output $target
