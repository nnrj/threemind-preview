param([int]$CorePort = 8877, [int]$UiPort = 3001)
$root = Split-Path -Parent $PSScriptRoot
$core = Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$root'; `$env:PYTHONPATH='core'; python -m threemind serve --port $CorePort" -PassThru
$ui = Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$root\threemind-ui'; npm run dev -- --port $UiPort" -PassThru
Write-Host "ThreeMind Core PID: $($core.Id)  http://127.0.0.1:$CorePort"
Write-Host "ThreeMind UI   PID: $($ui.Id)  http://127.0.0.1:$UiPort"
