[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$Doc,
    [Parameter(Mandatory = $true)][string]$Command,
    [Parameter(Mandatory = $true)][int]$ExpectedRevision,
    [string]$ContentFile,
    [string]$HighlightInventoryFile,
    [string]$BlockId,
    [string]$Pattern,
    [string]$SrcBlockIds,
    [ValidateSet('xml', 'markdown')][string]$DocFormat = 'xml',
    [int]$MinimumWhiteboards = 0,
    [int]$MinimumHighlights = 0,
    [double]$MaximumHighlightRatio = 0.30,
    [string]$BackupDirectory = '.feishu-backups',
    [switch]$Commit
)

$python = Get-Command python -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $python) { $python = Get-Command python3 -ErrorAction SilentlyContinue | Select-Object -First 1 }
if (-not $python) { throw 'Python 3.10+ is required.' }
$arguments = @(
    (Join-Path $PSScriptRoot 'invoke_feishu_update.py'), '--doc', $Doc, '--command', $Command,
    '--expected-revision', $ExpectedRevision, '--doc-format', $DocFormat,
    '--minimum-whiteboards', $MinimumWhiteboards, '--minimum-highlights', $MinimumHighlights,
    '--maximum-highlight-ratio', $MaximumHighlightRatio, '--backup-directory', $BackupDirectory
)
if ($ContentFile) { $arguments += @('--content-file', $ContentFile) }
if ($HighlightInventoryFile) { $arguments += @('--highlight-inventory-file', $HighlightInventoryFile) }
if ($BlockId) { $arguments += @('--block-id', $BlockId) }
if ($Pattern) { $arguments += @('--pattern', $Pattern) }
if ($SrcBlockIds) { $arguments += @('--src-block-ids', $SrcBlockIds) }
if ($Commit) { $arguments += '--commit' }
& $python.Source @arguments
exit $LASTEXITCODE
