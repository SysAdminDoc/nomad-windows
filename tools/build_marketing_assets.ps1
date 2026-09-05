[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
$magick = (Get-Command magick -ErrorAction Stop).Source
$screenshot = Join-Path $repoRoot 'docs\media\readiness-dashboard.png'
$logo = Join-Path $repoRoot 'web\static\logo.png'
$outputDir = Join-Path $repoRoot '.github'
$output = Join-Path $outputDir 'social-preview.png'

foreach ($required in $screenshot, $logo) {
    if (-not (Test-Path -LiteralPath $required)) {
        throw "Required marketing source not found: $required"
    }
}

New-Item -ItemType Directory -Path $outputDir -Force | Out-Null
$tempRoot = [System.IO.Path]::GetFullPath([System.IO.Path]::GetTempPath())
$tempDir = Join-Path $tempRoot ("nomad-social-" + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $tempDir | Out-Null

try {
    $background = Join-Path $tempDir 'background.png'
    $screen = Join-Path $tempDir 'screen.png'
    $mask = Join-Path $tempDir 'mask.png'
    $rounded = Join-Path $tempDir 'rounded.png'
    $mark = Join-Path $tempDir 'mark.png'
    $stage = Join-Path $tempDir 'stage.png'

    & $magick -size 1280x640 'gradient:#070b10-#172335' $background
    if ($LASTEXITCODE -ne 0) { throw 'Could not build social-card background.' }

    & $magick $screenshot -resize '700x438!' -strip $screen
    & $magick -size 700x438 xc:none -fill white -draw 'roundrectangle 0,0 699,437 22,22' $mask
    & $magick $screen $mask -alpha off -compose CopyOpacity -composite $rounded
    & $magick $background $rounded -geometry '+520+101' -composite `
        -stroke '#d9ad67' -strokewidth 2 -fill none -draw 'roundrectangle 519,100 1220,540 24,24' $stage
    if ($LASTEXITCODE -ne 0) { throw 'Could not place product screenshot.' }

    & $magick $logo -resize '142x142' -strip $mark
    & $magick $stage $mark -geometry '+74+66' -composite `
        -font 'Segoe-UI-Bold' -fill '#f6f2e9' -pointsize 66 -annotate '+72+287' 'NOMAD' `
        -font 'Segoe-UI-Semibold' -fill '#d9ad67' -pointsize 31 -annotate '+75+332' 'FIELD DESK' `
        -font 'Segoe-UI' -fill '#c7d0dd' -pointsize 25 -annotate '+75+396' 'Preparedness runs locally.' `
        -fill '#8e9bad' -pointsize 18 -annotate '+75+438' 'Plan, track, and reference' `
        -annotate '+75+468' 'without a cloud account.' `
        -fill '#d9ad67' -draw 'roundrectangle 75,510 398,555 22,22' `
        -font 'Segoe-UI-Semibold' -fill '#09111b' -pointsize 17 -annotate '+101+539' 'PRIVATE  |  OFFLINE READY' `
        -depth 8 -strip $output
    if ($LASTEXITCODE -ne 0) { throw 'Could not render social preview.' }
}
finally {
    $resolved = [System.IO.Path]::GetFullPath($tempDir)
    if ($resolved.StartsWith($tempRoot, [System.StringComparison]::OrdinalIgnoreCase) -and
        (Split-Path -Leaf $resolved) -like 'nomad-social-*') {
        Remove-Item -LiteralPath $resolved -Recurse -Force -ErrorAction SilentlyContinue
    }
}

Write-Host "Built $output"
