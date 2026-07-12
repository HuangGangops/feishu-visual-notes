[CmdletBinding()]
param([version]$MinimumVersion = [version]'1.0.67')

$python = Get-Command python -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $python) { $python = Get-Command python3 -ErrorAction SilentlyContinue | Select-Object -First 1 }
if (-not $python) { throw 'Python 3.10+ is required.' }
& $python.Source (Join-Path $PSScriptRoot 'resolve_lark_cli.py') --minimum-version $MinimumVersion.ToString()
if ($LASTEXITCODE -ne 0) { throw 'No compatible Lark/Feishu CLI was found.' }
