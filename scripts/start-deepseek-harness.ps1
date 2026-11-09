$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw "Docker CLI not found. Start Docker Desktop and reopen PowerShell."
}

$dockerOs = & docker info --format '{{.OSType}}' 2>$null
if ($LASTEXITCODE -ne 0 -or $dockerOs.Trim() -ne "linux") {
    throw "Docker Desktop is not ready with Linux containers."
}

$composeArgs = @("-f", "docker-compose.yml", "-f", "docker-compose.harness.yml")

# Avoid colliding with an unrelated local service on the UI port.
$existingState = & docker inspect --format '{{.State.Status}}' quantaedge-deepseek-harness 2>$null
if ($existingState -ne "running") {
    $listener = Get-NetTCPConnection -LocalPort 3080 -State Listen -ErrorAction SilentlyContinue |
        Select-Object -First 1
    if ($listener) {
        $owner = Get-Process -Id $listener.OwningProcess -ErrorAction SilentlyContinue
        throw "Port 3080 is already used by PID $($listener.OwningProcess) ($($owner.ProcessName)). Stop that service or choose another port."
    }
}

Write-Host "Starting DeepSeek Harness Web UI in Docker..." -ForegroundColor Green
& docker compose @composeArgs up -d deepseek-harness
if ($LASTEXITCODE -ne 0) {
    throw "Could not start DeepSeek Harness. Check Docker Compose output."
}

# DSH prints a one-time launch URL containing its process token.
# Capture it locally and hand it directly to the default browser.
$launchUrl = $null
for ($attempt = 0; $attempt -lt 90 -and -not $launchUrl; $attempt++) {
    $logLines = & docker compose @composeArgs logs --no-color --tail 100 deepseek-harness 2>&1
    foreach ($line in $logLines) {
        if ($line -match 'dsh web:\s+(https?://\S+)') {
            $launchUrl = $Matches[1].Trim()
            break
        }
    }
    if (-not $launchUrl) {
        Start-Sleep -Seconds 2
    }
}

if ($launchUrl) {
    Write-Host "DeepSeek Harness is ready. Opening its one-time local launch URL..." -ForegroundColor Green
    Start-Process -FilePath $launchUrl
    Write-Host "UI address: http://127.0.0.1:3080"
    Write-Host "Persistent Harness home: Docker volume quantaedge-harness-home"
    Write-Host "Persistent workspace: Docker volume quantaedge-harness-workspace"
} else {
    Write-Warning "The launch URL was not found yet. Review the container logs below."
    & docker compose @composeArgs logs --no-color --tail 100 deepseek-harness
    throw "DeepSeek Harness did not print its Web UI launch URL. Resolve any startup error and rerun this script."
}
