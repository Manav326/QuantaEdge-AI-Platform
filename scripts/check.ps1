$ErrorActionPreference = "Stop"
Write-Host "===== Docker infrastructure ====="
docker compose ps
Write-Host "===== Ollama ====="
Invoke-RestMethod http://127.0.0.1:11434/api/tags | ConvertTo-Json -Depth 6
Write-Host "===== AI API liveness ====="
Invoke-RestMethod http://127.0.0.1:8000/health | ConvertTo-Json
Write-Host "===== AI API readiness ====="
$envPath = Join-Path (Split-Path -Parent $PSScriptRoot) ".env"
$line = Get-Content $envPath | Where-Object { $_ -like "SERVICE_API_KEYS=*" } | Select-Object -First 1
if (-not $line) { throw "SERVICE_API_KEYS missing in .env" }
$keys = ($line -replace '^SERVICE_API_KEYS=', '') | ConvertFrom-Json
$adminKey = $keys.'local-admin'.key
Invoke-RestMethod http://127.0.0.1:8000/ready -Headers @{"X-API-Key"=$adminKey} | ConvertTo-Json -Depth 5
