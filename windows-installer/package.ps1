param(
    [string]$OutputDirectory = (Join-Path $PSScriptRoot 'dist'),
    [string]$AddonArchive = '',
    [string]$Version = ''
)
$ErrorActionPreference = 'Stop'
$repo = Split-Path $PSScriptRoot
if (-not $Version) {
    $match = [regex]::Match(
        (Get-Content -Raw -LiteralPath (Join-Path $repo 'roleweaver\__init__.py')),
        '__version__\s*=\s*"([^"]+)"'
    )
    if (-not $match.Success) { throw 'Application version could not be read.' }
    $Version = $match.Groups[1].Value
}
$built = & (Join-Path $PSScriptRoot 'build.ps1') -OutputDirectory $OutputDirectory
$zip = Join-Path ([IO.Path]::GetFullPath($OutputDirectory)) ("RoleWeaver-Remote-Installer-$Version.zip")
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
    $addonChecksum = $resolvedAddon + '.sha256'
    if (Test-Path -LiteralPath $addonChecksum -PathType Leaf) {
        $packagedChecksum = $packagedAddon + '.sha256'
        if ($addonChecksum -ne $packagedChecksum) {
            Copy-Item -LiteralPath $addonChecksum -Destination $packagedChecksum -Force
        }
        $payload += $packagedChecksum
    }
}
Compress-Archive -CompressionLevel Optimal -Path $payload -DestinationPath $zip
$hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $zip).Hash.ToLowerInvariant()
Set-Content -Encoding ASCII -NoNewline -LiteralPath ($zip + '.sha256') -Value ($hash + '  ' + [IO.Path]::GetFileName($zip) + "`n")
Write-Output $zip
