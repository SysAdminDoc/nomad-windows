[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
$source = Join-Path $repoRoot 'assets\nomad-field-desk-mark.svg'
$magick = (Get-Command magick -ErrorAction Stop).Source

if (-not (Test-Path -LiteralPath $source)) {
    throw "Brand source not found: $source"
}

$outputs = @(
    @{ Path = Join-Path $repoRoot 'logo.png'; Size = 1024 },
    @{ Path = Join-Path $repoRoot 'web\static\logo.png'; Size = 512 },
    @{ Path = Join-Path $repoRoot 'web\static\logo-192.png'; Size = 192 },
    @{ Path = Join-Path $repoRoot 'web\static\logo-512.png'; Size = 512 }
)

foreach ($output in $outputs) {
    & $magick -background none -density 384 $source -resize "$($output.Size)x$($output.Size)" -strip "PNG32:$($output.Path)"
    if ($LASTEXITCODE -ne 0) {
        throw "ImageMagick failed while building $($output.Path)"
    }
}

$maskableMark = Join-Path ([System.IO.Path]::GetTempPath()) 'nomad-maskable-mark.png'
$maskableOutput = Join-Path $repoRoot 'web\static\logo-maskable-512.png'
try {
    & $magick -background none -density 384 $source -resize '384x384' -strip "PNG32:$maskableMark"
    & $magick -size 512x512 'xc:#0b131d' $maskableMark -gravity center -composite -strip "PNG32:$maskableOutput"
    if ($LASTEXITCODE -ne 0) {
        throw 'ImageMagick failed while building the maskable PWA icon'
    }
}
finally {
    Remove-Item -LiteralPath $maskableMark -ErrorAction SilentlyContinue
}

$iconFrames = 16, 24, 32, 48, 64, 128, 256
$framePaths = foreach ($size in $iconFrames) {
    $frame = Join-Path ([System.IO.Path]::GetTempPath()) "nomad-icon-$size.png"
    & $magick -background none -density 384 $source -resize "${size}x${size}" -strip "PNG32:$frame"
    if ($LASTEXITCODE -ne 0) {
        throw "ImageMagick failed while building the ${size}px icon frame"
    }
    $frame
}

try {
    & $magick @framePaths (Join-Path $repoRoot 'icon.ico')
    if ($LASTEXITCODE -ne 0) {
        throw 'ImageMagick failed while building icon.ico'
    }
}
finally {
    foreach ($frame in $framePaths) {
        Remove-Item -LiteralPath $frame -ErrorAction SilentlyContinue
    }
}

Write-Host 'Built transparent NOMAD PNGs, a maskable PWA icon, and a seven-frame Windows icon.'
