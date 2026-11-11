param(
    [string]$Python = ".work/kernel-venv/Scripts/python.exe",
    [string]$PostgresBin = "D:/Program Files/PostgreSQL/17/bin",
    [ValidateRange(1024,65535)][int]$Port = 55439,
    [Parameter(ValueFromRemainingArguments = $true)][string[]]$PytestArgs
)
$ErrorActionPreference = 'Stop'
$workspace = Split-Path -Parent $PSScriptRoot
$cluster = Join-Path $workspace '.work/pgtest'
if (-not (Test-Path -LiteralPath (Join-Path $cluster 'PG_VERSION'))) {
    throw 'This helper uses an already provisioned .work/pgtest cluster; it never creates or replaces a database.'
}
$env:TEMP = Join-Path $workspace '.work/tmp'
$env:TMP = $env:TEMP
New-Item -ItemType Directory -Force -Path $env:TEMP | Out-Null
$control = Join-Path $PostgresBin 'pg_ctl.exe'
$env:THREEMIND_TEST_PG_PORT = [string]$Port
& $control status -D $cluster | Out-Null
$started = $LASTEXITCODE -ne 0
if (-not $started) {
    $pidLines = Get-Content -LiteralPath (Join-Path $cluster 'postmaster.pid')
    if ($pidLines[3] -ne [string]$Port) { throw 'Existing test cluster is on a different port. Use that port explicitly; this helper will not stop an existing service.' }
}
if ($started) {
    # Keep live logs outside PGDATA: Windows recovery may otherwise hit a sharing
    # violation while syncing the cluster after an interrupted test host.
    & $control start -D $cluster -o "-p $Port -h 127.0.0.1" -l (Join-Path $workspace '.work/pgtest-server.log') -w -t 30
    if ($LASTEXITCODE -ne 0) { throw "Could not start the isolated test cluster on port $Port." }
}
try {
    & (Join-Path $workspace $Python) -m pytest @PytestArgs
    $testExit = $LASTEXITCODE
} finally {
    if ($started) { & $control stop -D $cluster -m fast -w -t 20 }
}
exit $testExit
