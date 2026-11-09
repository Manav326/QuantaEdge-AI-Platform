$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
if (-not (Test-Path "$root\.venv\Scripts\python.exe")) { throw "Run .\scripts\initialize.ps1 first." }
$env:PYTHONPATH = "$root\apps\api"
$env:CONFIG_DIR = "$root\config"
$env:DATA_DIR = "D:\QuantaEdgeAI\data"
$ollama = Invoke-RestMethod -Uri "http://127.0.0.1:11434/api/tags" -TimeoutSec 5
if (-not $ollama) { throw "Ollama is not responding at 127.0.0.1:11434." }
Write-Host "Starting QuantaEdge AI API on http://127.0.0.1:8000" -ForegroundColor Green
& "$root\.venv\Scripts\python.exe" -m uvicorn app.main:app --app-dir "$root\apps\api" --host 127.0.0.1 --port 8000
