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

$volume = "quantaedge-cloudflare-tunnel-token"
& docker volume inspect $volume *> $null
if ($LASTEXITCODE -ne 0) {
    throw "Docker token volume is missing. Run .\scripts\set-cloudflare-tunnel-token.ps1 to provision it."
}

& docker run --rm --mount "type=volume,source=$volume,target=/run/secrets,readonly" alpine:3.20 sh -c "test -s /run/secrets/cloudflare_tunnel_token"
if ($LASTEXITCODE -ne 0) {
    throw "The Docker-managed tunnel-token volume is empty or unreadable. Re-run set-cloudflare-tunnel-token.ps1."
}

Write-Host "Starting the Cloudflare Tunnel connector in Docker..." -ForegroundColor Green
& docker compose -f docker-compose.yml -f docker-compose.cloudflare.yml up -d cloudflared
if ($LASTEXITCODE -ne 0) {
    throw "Could not start cloudflared. Check Docker Desktop host networking and connector logs."
}

& docker compose -f docker-compose.yml -f docker-compose.cloudflare.yml ps cloudflared
