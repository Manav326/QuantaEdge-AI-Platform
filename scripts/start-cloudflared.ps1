param(
    [string]$TokenPath = "D:\QuantaEdgeAI\secrets\cloudflare-tunnel.token"
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw "Docker CLI not found. Start Docker Desktop and reopen PowerShell."
}
if (-not (Test-Path $TokenPath -PathType Leaf)) {
    throw "Tunnel token file not found. Run .\scripts\set-cloudflare-tunnel-token.ps1 first."
}

$dockerOs = & docker info --format '{{.OSType}}' 2>$null
if ($LASTEXITCODE -ne 0 -or $dockerOs.Trim() -ne "linux") {
    throw "Docker Desktop is not ready with Linux containers. Start Docker Desktop and verify its Linux engine."
}

# Compose uses this only to identify the secret source path.
# The token itself is never added to the environment or command line.
$env:CLOUDFLARE_TUNNEL_TOKEN_FILE = ($TokenPath -replace '\\', '/')

Write-Host "Starting the Cloudflare Tunnel connector in Docker..." -ForegroundColor Green
& docker compose -f docker-compose.yml -f docker-compose.cloudflare.yml up -d cloudflared
if ($LASTEXITCODE -ne 0) {
    throw "Could not start cloudflared. Verify Docker Desktop host networking (4.34+) is enabled and the secret file is readable."
}

& docker compose -f docker-compose.yml -f docker-compose.cloudflare.yml ps cloudflared