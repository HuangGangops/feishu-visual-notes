[CmdletBinding()]
param([string]$OutputDirectory, [switch]$Force)

$python = Get-Command python -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $python) { $python = Get-Command python3 -ErrorAction SilentlyContinue | Select-Object -First 1 }
if (-not $python) { throw 'Python 3.10+ is required.' }
$arguments = @((Join-Path $PSScriptRoot 'package_release.py'))
if ($OutputDirectory) { $arguments += @('--output-directory', $OutputDirectory) }
if ($Force) { $arguments += '--force' }
& $python.Source @arguments
exit $LASTEXITCODE
