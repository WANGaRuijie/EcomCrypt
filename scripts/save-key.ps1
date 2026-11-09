# Save an API key encrypted with Windows DPAPI (readable only by this Windows account),
# in the same place expand.ps1 / discover.ps1 / monthly.ps1 load keys from.
#   & .\scripts\save-key.ps1 semanticscholar
param([Parameter(Mandatory=$true)][ValidateSet('openalex','deepseek','semanticscholar')][string]$Provider)
$ErrorActionPreference = 'Stop'
$store = Join-Path $env:LOCALAPPDATA 'EconCSDirectory'
New-Item -ItemType Directory -Force -Path $store | Out-Null
$secure = Read-Host "$Provider API key" -AsSecureString
$secure | ConvertFrom-SecureString | Set-Content -LiteralPath (Join-Path $store "$Provider.dpapi")
Write-Host "Saved: $(Join-Path $store "$Provider.dpapi")"
