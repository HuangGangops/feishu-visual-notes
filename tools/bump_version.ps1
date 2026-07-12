[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][ValidateSet('major', 'minor', 'patch')][string]$Bump,
    [Parameter(Mandatory = $true)][string[]]$Change,
    [switch]$Commit
)

$python = Get-Command python -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $python) { $python = Get-Command python3 -ErrorAction SilentlyContinue | Select-Object -First 1 }
if (-not $python) { throw 'Python 3.10+ is required.' }
$arguments = @((Join-Path $PSScriptRoot 'bump_version.py'), '--bump', $Bump)
foreach ($item in $Change) { $arguments += @('--change', $item) }
if ($Commit) { $arguments += '--commit' }
& $python.Source @arguments
exit $LASTEXITCODE
