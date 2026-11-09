$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
if (-not (Test-Path "$root\.env")) { throw "Missing .env. Run .\scripts\initialize.ps1 first." }
docker compose up -d postgres redis
if ($LASTEXITCODE -ne 0) { throw "Docker Compose failed to start infrastructure." }
docker compose ps
