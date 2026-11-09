$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$required = @(
    "D:\QuantaEdgeAI\models\ollama",
    "D:\QuantaEdgeAI\data\uploads",
    "D:\QuantaEdgeAI\data\processed",
    "D:\QuantaEdgeAI\logs",
    "D:\QuantaEdgeAI\backups"
)
foreach ($path in $required) { New-Item -ItemType Directory -Force -Path $path | Out-Null }

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    throw "Python is not installed or not on PATH. Install Python 3.12, reopen PowerShell, then rerun scripts\initialize.ps1."
}
$pythonVersion = & python --version 2>&1
if ($pythonVersion -notmatch "Python 3\.12\.") {
    throw "This project is pinned to Python 3.12. Detected: $pythonVersion. Install Python 3.12 and rerun."
}

if (-not (Test-Path "$root\.venv\Scripts\python.exe")) {
    & python -m venv "$root\.venv"
}
$venvPython = "$root\.venv\Scripts\python.exe"
& $venvPython -m pip install --upgrade pip
& $venvPython -m pip install -r "$root\apps\api\requirements.txt"

if (-not (Test-Path "$root\.env")) {
    function New-SecretHex([int]$bytesCount = 32) {
        $bytes = New-Object byte[] $bytesCount
        $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
        try { $rng.GetBytes($bytes) } finally { $rng.Dispose() }
        return ([BitConverter]::ToString($bytes) -replace "-", "").ToLowerInvariant()
    }

    $dbPassword = New-SecretHex 32
    $adminKey = New-SecretHex 48
    $backendKey = New-SecretHex 48
    $harnessKey = New-SecretHex 48
    $keys = [ordered]@{
        "local-admin" = @{ key = $adminKey; scopes = @("*") }
        "quantaedge-backend" = @{ key = $backendKey; scopes = @("chat", "learning", "embeddings", "models:read", "knowledge:read", "memory:read", "memory:write", "memory:delete") }
        "deepseek-harness" = @{ key = $harnessKey; scopes = @("chat", "models:read") }
    }
    $keysJson = $keys | ConvertTo-Json -Depth 6 -Compress
    $envText = @"
ENVIRONMENT=development
LOG_LEVEL=INFO
POSTGRES_DB=quantaedge_ai
POSTGRES_USER=qeai
POSTGRES_PASSWORD=$dbPassword
DATABASE_URL=postgresql+asyncpg://qeai:$dbPassword@127.0.0.1:5432/quantaedge_ai
REDIS_URL=redis://127.0.0.1:6379/0
OLLAMA_BASE_URL=http://127.0.0.1:11434
CONFIG_DIR=$($root -replace '\\','/')/config
DATA_DIR=D:/QuantaEdgeAI/data
SERVICE_API_KEYS=$keysJson
API_REQUEST_TIMEOUT_SECONDS=180
"@
    [System.IO.File]::WriteAllText("$root\.env", $envText, (New-Object System.Text.UTF8Encoding($false)))
    Write-Host "Created .env with unique random credentials. Keep it private."
    Write-Host "QuantaEdge backend API key (store in backend secret manager): $backendKey" -ForegroundColor Yellow
    Write-Host "DeepSeek Harness API key (store in Harness provider settings): $harnessKey" -ForegroundColor Yellow
    Write-Host "Local admin API key (store securely): $adminKey" -ForegroundColor Yellow
} else {
    Write-Host ".env already exists; left unchanged." -ForegroundColor Yellow
}

Write-Host "Initialization complete. Next: .\scripts\start-infrastructure.ps1" -ForegroundColor Green
