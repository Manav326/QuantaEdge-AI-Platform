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

# Check running containers without inspecting a container that may not exist.
$runningContainers = & docker ps --filter "name=quantaedge-deepseek-harness" --format "{{.Names}}" 2>$null
if ($LASTEXITCODE -ne 0) {
    throw "Could not query Docker containers. Check that Docker Desktop is running."
}
$harnessIsRunning = $runningContainers -contains "quantaedge-deepseek-harness"

# Avoid colliding with an unrelated local service on the UI port.
if (-not $harnessIsRunning) {
    $listener = Get-NetTCPConnection -LocalPort 3080 -State Listen -ErrorAction SilentlyContinue |
        Select-Object -First 1
    if ($listener) {
        $owner = Get-Process -Id $listener.OwningProcess -ErrorAction SilentlyContinue
        $processName = if ($owner) { $owner.ProcessName } else { "unknown" }
        throw "Port 3080 is already used by PID $($listener.OwningProcess) ($processName). Stop that service or choose another port."
    }
}

Write-Host "Starting DeepSeek Harness Web UI in Docker..." -ForegroundColor Green
& docker compose @composeArgs up -d deepseek-harness
if ($LASTEXITCODE -ne 0) {
    throw "Could not start DeepSeek Harness. Check Docker Compose output."
}

# Read container stdout/stderr directly. Compose interpolates dollar expressions
# while parsing YAML, so using compose logs here can surface unrelated warnings.
# Windows PowerShell 5.1 also promotes native stderr to NativeCommandError when
# ErrorActionPreference is Stop; temporarily allow it while collecting logs.
$launchUrl = $null
$lastLogLines = @()
for ($attempt = 0; $attempt -lt 90 -and -not $launchUrl; $attempt++) {
    $previousPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = "Continue"
        $lastLogLines = @(& docker logs --tail 100 quantaedge-deepseek-harness 2>&1 | ForEach-Object { "$_" })
    }
    finally {
        $ErrorActionPreference = $previousPreference
    }

    foreach ($line in $lastLogLines) {
        if ($line -match 'dsh web:\s+(https?://\S+)') {
            $launchUrl = $Matches[1].Trim()
            break
        }
    }

    if (-not $launchUrl) {
        $state = & docker inspect --format '{{.State.Status}}' quantaedge-deepseek-harness 2>$null
        if ($LASTEXITCODE -eq 0 -and $state -eq "exited") {
            break
        }
        Start-Sleep -Seconds 2
    }
}

if ($launchUrl) {
    Write-Host "DeepSeek Harness is ready. Opening its one-time local launch URL..." -ForegroundColor Green
    Start-Process -FilePath $launchUrl
    Write-Host "UI address: http://127.0.0.1:3080"
    Write-Host "Persistent Harness home: Docker volume quantaedge-harness-home"
    Write-Host "Persistent workspace: Docker volume quantaedge-harness-workspace"
}
else {
    Write-Warning "Harness did not print its one-time launch URL. Recent diagnostic output (URL tokens omitted):"
    $lastLogLines |
        Where-Object { $_ -notmatch 'dsh web:\s+https?://' } |
        Select-Object -Last 15 |
        ForEach-Object { Write-Host $_ }
    throw "DeepSeek Harness did not become ready. Check the container logs and correct the startup error."
}
