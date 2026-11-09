param([Parameter(ValueFromRemainingArguments=$true)][string[]]$ExpansionArgs)
$ErrorActionPreference = 'Stop'
$store = Join-Path $env:LOCALAPPDATA 'EconCSDirectory'
$loaded = @()
try {
    foreach ($provider in 'openalex', 'deepseek') {
        $name = $provider.ToUpperInvariant() + '_API_KEY'
        if (-not (Test-Path "Env:$name")) {
            $file = Join-Path $store ($provider + '.dpapi')
            $secret = Get-Content -LiteralPath $file | ConvertTo-SecureString
            Set-Item "Env:$name" ([System.Net.NetworkCredential]::new('', $secret).Password)
            $loaded += $name
        }
    }
} catch {
    foreach ($name in $loaded) { Remove-Item "Env:$name" }
    throw 'Could not load saved credentials. Run from the Windows account that saved them.'
}
try {
    python (Join-Path $PSScriptRoot 'expand.py') @ExpansionArgs
    exit $LASTEXITCODE
} finally {
    foreach ($name in $loaded) { Remove-Item "Env:$name" }
}
