$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
if (-not (Test-Path "$root\.venv\Scripts\python.exe")) { throw "Run .\scripts\initialize.ps1 first." }
$env:PYTHONPATH = "$root\apps\api"
$env:CONFIG_DIR = "$root\config"
$env:DATA_DIR = "D:\QuantaEdgeAI\data"
Write-Host "Starting QuantaEdge ingestion worker. Keep this terminal open." -ForegroundColor Green
& "$root\.venv\Scripts\python.exe" -m arq app.worker.WorkerSettings
