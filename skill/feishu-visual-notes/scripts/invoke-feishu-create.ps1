[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$ContentFile,
    [string]$HighlightInventoryFile,
    [ValidateSet('xml', 'markdown')][string]$DocFormat = 'xml',
    [string]$ParentToken,
    [string]$ParentPosition,
    [int]$MinimumWhiteboards = 0,
    [int]$MinimumHighlights = 0,
    [double]$MaximumHighlightRatio = 0.30,
    [switch]$Commit
)

$python = Get-Command python -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $python) { $python = Get-Command python3 -ErrorAction SilentlyContinue | Select-Object -First 1 }
if (-not $python) { throw 'Python 3.10+ is required.' }
$arguments = @(
    (Join-Path $PSScriptRoot 'invoke_feishu_create.py'), '--content-file', $ContentFile,
    '--doc-format', $DocFormat, '--minimum-whiteboards', $MinimumWhiteboards,
    '--minimum-highlights', $MinimumHighlights, '--maximum-highlight-ratio', $MaximumHighlightRatio
)
if ($HighlightInventoryFile) { $arguments += @('--highlight-inventory-file', $HighlightInventoryFile) }
if ($ParentToken) { $arguments += @('--parent-token', $ParentToken) }
if ($ParentPosition) { $arguments += @('--parent-position', $ParentPosition) }
if ($Commit) { $arguments += '--commit' }
& $python.Source @arguments
exit $LASTEXITCODE
