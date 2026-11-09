# Monthly pipeline wrapper: temporarily loads saved API keys (Windows DPAPI, this
# account only) and runs scripts/monthly.py. Keys already in the environment win;
# keys loaded here are removed again on exit. Missing optional keys are skipped.
param([Parameter(ValueFromRemainingArguments=$true)][string[]]$PipelineArgs)
$ErrorActionPreference = 'Stop'
$store = Join-Path $env:LOCALAPPDATA 'EconCSDirectory'
$map = [ordered]@{ openalex = 'OPENALEX_API_KEY'; deepseek = 'DEEPSEEK_API_KEY'; semanticscholar = 'S2_API_KEY' }
$loaded = @()
try {
    foreach ($provider in $map.Keys) {
        $name = $map[$provider]
        if (Test-Path "Env:$name") { continue }
        $file = Join-Path $store ($provider + '.dpapi')
        if (-not (Test-Path -LiteralPath $file)) { continue }
        $secret = Get-Content -LiteralPath $file | ConvertTo-SecureString
        Set-Item "Env:$name" ([System.Net.NetworkCredential]::new('', $secret).Password)
        $loaded += $name
    }
    $mailto = Join-Path $store 'crossref-mailto.txt'
    if (-not (Test-Path 'Env:CROSSREF_MAILTO') -and (Test-Path -LiteralPath $mailto)) {
        Set-Item 'Env:CROSSREF_MAILTO' (Get-Content -LiteralPath $mailto -TotalCount 1).Trim()
        $loaded += 'CROSSREF_MAILTO'
    }
    python (Join-Path $PSScriptRoot 'monthly.py') @PipelineArgs
    exit $LASTEXITCODE
} catch {
    throw "monthly.ps1: $($_.Exception.Message)"
} finally {
    foreach ($name in $loaded) { Remove-Item "Env:$name" -ErrorAction SilentlyContinue }
}
