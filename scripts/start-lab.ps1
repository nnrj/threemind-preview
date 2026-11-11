param([int]$Port = 8877, [string]$Python)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Push-Location -LiteralPath $projectRoot
try {
    $env:PYTHONPATH = Join-Path $projectRoot 'src'
    $pythonPath = if ($Python) { (Resolve-Path -LiteralPath $Python).Path } else { Join-Path $projectRoot '.venv\Scripts\python.exe' }
    if (-not (Test-Path -LiteralPath $pythonPath)) { throw 'Install the project first; see docs/zh/v2-operations.md' }
    & $pythonPath -m threemind_lab.cli workstation --port $Port
} finally { Pop-Location }
