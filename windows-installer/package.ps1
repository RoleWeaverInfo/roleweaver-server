param([string]$OutputDirectory = (Join-Path $PSScriptRoot 'dist'))
$ErrorActionPreference = 'Stop'
$built = & (Join-Path $PSScriptRoot 'build.ps1') -OutputDirectory $OutputDirectory
$zip = Join-Path ([IO.Path]::GetFullPath($OutputDirectory)) 'RoleWeaver-Remote-Installer-1.0.0.zip'
if (Test-Path $zip) { Remove-Item -LiteralPath $zip }
Compress-Archive -CompressionLevel Optimal -Path $built,(Join-Path ([IO.Path]::GetFullPath($OutputDirectory)) 'README.txt') -DestinationPath $zip
$hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $zip).Hash.ToLowerInvariant()
Set-Content -Encoding ASCII -NoNewline -LiteralPath ($zip + '.sha256') -Value ($hash + '  ' + [IO.Path]::GetFileName($zip) + "`n")
Write-Output $zip
