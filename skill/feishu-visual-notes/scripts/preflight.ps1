[CmdletBinding()]
param(
    [switch]$Json,
    [switch]$Interactive,
    [switch]$CheckFeishu,
    [switch]$Offline,
    [string]$CapabilitiesFile,
    [switch]$Save
)

$ErrorActionPreference = 'Stop'
$python = Get-Command python -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $python) {
    $python = Get-Command python3 -ErrorAction SilentlyContinue | Select-Object -First 1
}
if (-not $python) {
    throw 'Python 3.10+ is required. Install it, then run this check again.'
}
$arguments = @((Join-Path $PSScriptRoot 'preflight.py'))
if ($Json) { $arguments += '--json' }
if ($Interactive) { $arguments += '--interactive' }
if ($CheckFeishu) { $arguments += '--check-feishu' }
if ($Offline) { $arguments += '--offline' }
if ($CapabilitiesFile) { $arguments += @('--capabilities-file', $CapabilitiesFile) }
if ($Save) { $arguments += '--save' }
& $python.Source @arguments
exit $LASTEXITCODE
