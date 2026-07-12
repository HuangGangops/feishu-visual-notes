[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$Path,
    [int]$MinimumWhiteboards = 0,
    [int]$MinimumHighlights = 0,
    [double]$MaximumHighlightRatio = 0.30
)

$python = Get-Command python -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $python) { $python = Get-Command python3 -ErrorAction SilentlyContinue | Select-Object -First 1 }
if (-not $python) { throw 'Python 3.10+ is required.' }
& $python.Source (Join-Path $PSScriptRoot 'validate_visual_source.py') --input $Path `
    --minimum-whiteboards $MinimumWhiteboards --minimum-highlights $MinimumHighlights `
    --maximum-highlight-ratio $MaximumHighlightRatio
if ($LASTEXITCODE -ne 0) { throw 'Visual source validation failed.' }
