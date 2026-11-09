$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
$composeArgs = @("-f", "docker-compose.yml", "-f", "docker-compose.harness.yml")

& docker compose @composeArgs stop deepseek-harness
if ($LASTEXITCODE -ne 0) {
    throw "Could not stop DeepSeek Harness."
}

Write-Host "DeepSeek Harness stopped. Its home, sessions, credentials, npm cache and workspace volumes were preserved." -ForegroundColor Green
