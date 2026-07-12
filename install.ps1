[CmdletBinding()]
param([string]$DestinationRoot, [switch]$Force, [switch]$Json)

$arguments = @{}
if ($DestinationRoot) { $arguments.DestinationRoot = $DestinationRoot }
if ($Force) { $arguments.Force = $true }
if ($Json) { $arguments.Json = $true }
& (Join-Path $PSScriptRoot 'skill\feishu-visual-notes\scripts\install.ps1') @arguments
exit $LASTEXITCODE
