# First full pass: init (offline) -> DBLP monthly dump -> feeds + screening (dry run, no directory changes).
$ErrorActionPreference = 'Continue'
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
New-Item -ItemType Directory -Force -Path (Join-Path $root '.out\monthly') | Out-Null
$log = Join-Path $root '.out\monthly\run-log.txt'
$env:PYTHONUNBUFFERED = '1'
function Step($label, [string[]]$arguments) {
    "==== $label  $(Get-Date -Format s) ====" | Tee-Object -FilePath $log -Append
    & (Join-Path $PSScriptRoot 'monthly.ps1') @arguments 2>&1 | ForEach-Object { "$_" } | Tee-Object -FilePath $log -Append
    "==== exit code $LASTEXITCODE ====" | Tee-Object -FilePath $log -Append
}
"run-first-time started $(Get-Date -Format s)" | Set-Content -LiteralPath $log
Step 'init' @('init')
Step 'dblp' @('dblp', '--download')
Step 'run (dry run)' @('run', '--budget', '2')
Step 'status' @('status')
