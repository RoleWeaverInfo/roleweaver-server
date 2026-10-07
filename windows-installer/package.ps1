param(
    [string]$OutputDirectory = (Join-Path $PSScriptRoot 'dist'),
    [string]$AddonArchive = ''
)
$ErrorActionPreference = 'Stop'
$built = & (Join-Path $PSScriptRoot 'build.ps1') -OutputDirectory $OutputDirectory
$zip = Join-Path ([IO.Path]::GetFullPath($OutputDirectory)) 'RoleWeaver-Remote-Installer-1.0.0.zip'
if (Test-Path $zip) { Remove-Item -LiteralPath $zip }
$payload = @($built, (Join-Path ([IO.Path]::GetFullPath($OutputDirectory)) 'README.txt'))
if ($AddonArchive) {
    $resolvedAddon = [IO.Path]::GetFullPath($AddonArchive)
    if (-not (Test-Path -LiteralPath $resolvedAddon -PathType Leaf)) {
        throw "Server Add-on archive not found: $resolvedAddon"
    }
    $packagedAddon = Join-Path ([IO.Path]::GetFullPath($OutputDirectory)) ([IO.Path]::GetFileName($resolvedAddon))
    if ($resolvedAddon -ne $packagedAddon) {
        Copy-Item -LiteralPath $resolvedAddon -Destination $packagedAddon -Force
    }
    $payload += $packagedAddon
}
Compress-Archive -CompressionLevel Optimal -Path $payload -DestinationPath $zip
$hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $zip).Hash.ToLowerInvariant()
Set-Content -Encoding ASCII -NoNewline -LiteralPath ($zip + '.sha256') -Value ($hash + '  ' + [IO.Path]::GetFileName($zip) + "`n")
Write-Output $zip
