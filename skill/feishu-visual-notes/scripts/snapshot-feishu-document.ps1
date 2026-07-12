[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$Doc,
    [Parameter(Mandatory = $true)][int]$ExpectedRevision,
    [string]$OutputDirectory = '.feishu-backups'
)

$python = Get-Command python -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $python) { $python = Get-Command python3 -ErrorAction SilentlyContinue | Select-Object -First 1 }
if (-not $python) { throw 'Python 3.10+ is required.' }
& $python.Source (Join-Path $PSScriptRoot 'snapshot_feishu_document.py') --doc $Doc `
    --expected-revision $ExpectedRevision --output-directory $OutputDirectory
exit $LASTEXITCODE
