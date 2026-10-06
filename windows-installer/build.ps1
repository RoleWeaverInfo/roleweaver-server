param([string]$OutputDirectory = (Join-Path $PSScriptRoot 'dist'))
$ErrorActionPreference = 'Stop'
$output = [IO.Path]::GetFullPath($OutputDirectory)
New-Item -ItemType Directory -Force -Path $output | Out-Null
$compiler = Join-Path $env:WINDIR 'Microsoft.NET\Framework64\v4.0.30319\csc.exe'
if (-not (Test-Path $compiler)) { throw 'The Windows .NET Framework C# compiler is unavailable.' }
$target = Join-Path $output 'Role Weaver Remote Installer.exe'
& $compiler /nologo /target:winexe /platform:x64 /optimize+ "/out:$target" /reference:System.Windows.Forms.dll /reference:System.Drawing.dll (Join-Path $PSScriptRoot 'launcher\Program.cs')
if ($LASTEXITCODE -ne 0) { throw 'Remote installer compilation failed.' }
Copy-Item -Force (Join-Path $PSScriptRoot 'README.txt') (Join-Path $output 'README.txt')
Write-Output $target
