param(
    [Parameter(Mandatory=$true)][ValidateSet('authors','citations','parallel','sweep')][string]$Mode,
    [Parameter(ValueFromRemainingArguments=$true)][string[]]$DiscoveryArgs
)
$ErrorActionPreference = 'Stop'
$loadedKey = $false
try {
    if (-not (Test-Path Env:OPENALEX_API_KEY)) {
        $store = Join-Path $env:LOCALAPPDATA 'EconCSDirectory/openalex.dpapi'
        $secret = Get-Content -LiteralPath $store | ConvertTo-SecureString
        $env:OPENALEX_API_KEY = [System.Net.NetworkCredential]::new('', $secret).Password
        $loadedKey = $true
    }
    $module = @{authors='author_discovery.py';citations='harvest.py';parallel='discovery_parallel.py';sweep='bibliography_sweep.py'}[$Mode]
    python (Join-Path $PSScriptRoot $module) @DiscoveryArgs
    exit $LASTEXITCODE
} finally {
    if ($loadedKey) { Remove-Item Env:OPENALEX_API_KEY }
}
