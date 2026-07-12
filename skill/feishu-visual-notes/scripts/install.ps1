[CmdletBinding()]
param(
    [string]$DestinationRoot,
    [switch]$Force,
    [switch]$Json
)

$ErrorActionPreference = 'Stop'
$python = Get-Command python -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $python) { $python = Get-Command python3 -ErrorAction SilentlyContinue | Select-Object -First 1 }
if (-not $python) { throw 'Python 3.10+ is required.' }
$arguments = @((Join-Path $PSScriptRoot 'install.py'))
if ($DestinationRoot) { $arguments += @('--destination-root', $DestinationRoot) }
if ($Force) { $arguments += '--force' }
if ($Json) { $arguments += '--json' }
& $python.Source @arguments
exit $LASTEXITCODE
