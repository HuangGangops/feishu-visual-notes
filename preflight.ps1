[CmdletBinding()]
param([switch]$Json, [switch]$Interactive, [switch]$CheckFeishu, [switch]$Offline, [string]$CapabilitiesFile, [switch]$Save)

$arguments = @{}
if ($Json) { $arguments.Json = $true }
if ($Interactive) { $arguments.Interactive = $true }
if ($CheckFeishu) { $arguments.CheckFeishu = $true }
if ($Offline) { $arguments.Offline = $true }
if ($CapabilitiesFile) { $arguments.CapabilitiesFile = $CapabilitiesFile }
if ($Save) { $arguments.Save = $true }
& (Join-Path $PSScriptRoot 'skill\feishu-visual-notes\scripts\preflight.ps1') @arguments
exit $LASTEXITCODE
