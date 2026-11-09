param(
    [switch]$Rotate
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$envPath = Join-Path $root ".env"

if (-not (Test-Path $envPath)) {
    throw "Local .env was not found. Run .\scripts\initialize.ps1 first."
}

$lines = [System.IO.File]::ReadAllLines($envPath)
$lineIndex = -1
for ($i = 0; $i -lt $lines.Length; $i++) {
    if ($lines[$i].StartsWith("SERVICE_API_KEYS=")) {
        $lineIndex = $i
        break
    }
}
if ($lineIndex -lt 0) {
    throw "SERVICE_API_KEYS is missing from .env. Do not create a second credential store."
}

$json = $lines[$lineIndex].Substring("SERVICE_API_KEYS=".Length)
try {
    $records = ConvertFrom-Json -InputObject $json
} catch {
    throw "SERVICE_API_KEYS is not valid JSON. Correct .env before continuing."
}
if ($null -eq $records -or $records -isnot [pscustomobject]) {
    throw "SERVICE_API_KEYS must contain a JSON object."
}

$existing = $records.PSObject.Properties["deepseek-harness"]
if ($existing -and -not $Rotate) {
    Write-Host "The dedicated DeepSeek Harness credential already exists." -ForegroundColor Yellow
    Write-Host "No key was changed. Use the existing key from the local .env file."
    exit 0
}

function New-SecretHex([int]$bytesCount = 48) {
    $bytes = New-Object byte[] $bytesCount
    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try { $rng.GetBytes($bytes) } finally { $rng.Dispose() }
    return ([BitConverter]::ToString($bytes) -replace "-", "").ToLowerInvariant()
}

$harnessKey = New-SecretHex 48
$harnessRecord = [pscustomobject]@{
    key = $harnessKey
    scopes = @("chat", "models:read")
}
$records | Add-Member -MemberType NoteProperty -Name "deepseek-harness" -Value $harnessRecord -Force
$lines[$lineIndex] = "SERVICE_API_KEYS=" + ($records | ConvertTo-Json -Depth 10 -Compress)

# Preserve the existing local environment and all other service credentials.
$encoding = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllLines($envPath, $lines, $encoding)

Write-Host ""
Write-Host "Dedicated DeepSeek Harness credential added to .env." -ForegroundColor Green
Write-Host "Provider API key (copy into DeepSeek Harness once):" -ForegroundColor Yellow
Write-Host $harnessKey
Write-Host ""
Write-Host "Scopes: chat, models:read"
Write-Host "Keep this key private. Do not put it in Git, React, or Android."
if ($Rotate) {
    Write-Host "The previous DeepSeek Harness key is now invalid." -ForegroundColor Yellow
}
