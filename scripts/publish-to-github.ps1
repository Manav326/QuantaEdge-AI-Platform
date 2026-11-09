$ErrorActionPreference = "Stop"

$repoUrl = "https://github.com/Manav326/QuantaEdge-AI-Platform.git"
$repoPath = "D:\QuantaEdgeAI\projects\knowledge-engine"
$sourcePath = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path

if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    throw "Git for Windows is not installed or not on PATH. Install it with: winget install --id Git.Git -e --source winget. Then reopen PowerShell."
}
if (-not (Get-Command gh -ErrorAction SilentlyContinue)) {
    throw "GitHub CLI is not installed or not on PATH. Install it with: winget install --id GitHub.cli -e --source winget. Then reopen PowerShell."
}

& gh auth status
if ($LASTEXITCODE -ne 0) { throw "GitHub CLI is not authenticated. Run: gh auth login" }

New-Item -ItemType Directory -Force -Path (Split-Path -Parent $repoPath) | Out-Null
if (-not (Test-Path (Join-Path $repoPath ".git"))) {
    $existing = @(Get-ChildItem -LiteralPath $repoPath -Force -ErrorAction SilentlyContinue)
    if ($existing.Count -gt 0) {
        throw "Target folder is not empty and is not a Git repository: $repoPath. Move its contents safely or choose an empty folder. Nothing was deleted."
    }
    & git clone $repoUrl $repoPath
    if ($LASTEXITCODE -ne 0) { throw "Could not clone $repoUrl" }
}

& git -C $repoPath switch main
if ($LASTEXITCODE -ne 0) { throw "Could not switch the local repository to main." }

# Copy source and configuration only. This does not copy local .env, model weights,
# database files, Docker virtual disks, uploaded documents, logs or backups.
& robocopy $sourcePath $repoPath /E /COPY:DAT /R:2 /W:1 /XD ".git" ".venv" "__pycache__" ".pytest_cache" /XF ".env" "*.pyc" "*.pyo"
$robocopyCode = $LASTEXITCODE
if ($robocopyCode -ge 8) { throw "Source copy failed (robocopy exit code $robocopyCode)." }

& git -C $repoPath add --all
if ($LASTEXITCODE -ne 0) { throw "git add failed." }

$staged = @(& git -C $repoPath diff --cached --name-only)
$blocked = @($staged | Where-Object {
    $_ -match '(^|/)(models|data|backups|logs|downloads)(/|$)' -or
    $_ -match '(^|/)\.env$' -or
    $_ -match 'DockerDesktopWSL|credentials\.json$|\.(pem|p12|pfx|key)$'
})
if ($blocked.Count -gt 0) {
    & git -C $repoPath reset
    throw "Unsafe paths were staged and have been unstaged: $($blocked -join ', ')"
}

if ($staged.Count -eq 0) {
    Write-Host "No source changes to commit. Repository is already up to date." -ForegroundColor Green
    exit 0
}

if (-not (& git -C $repoPath config user.name)) {
    & git -C $repoPath config user.name "Manav Gupta"
}
if (-not (& git -C $repoPath config user.email)) {
    $ghEmail = (& gh api user --jq '.email // empty' 2>$null).Trim()
    if (-not $ghEmail) {
        throw "Git commit email is not configured. Set it with: git config --global user.email YOUR_GITHUB_EMAIL, then rerun this script."
    }
    & git -C $repoPath config user.email $ghEmail
}

Write-Host "Staged source files:" -ForegroundColor Cyan
$staged | ForEach-Object { Write-Host "  $_" }
Write-Host "Review the staged file list above. This script excludes runtime data and secrets." -ForegroundColor Yellow

& git -C $repoPath commit -m "feat: add QuantaEdge AI server baseline"
if ($LASTEXITCODE -ne 0) { throw "Git commit failed." }
& git -C $repoPath push -u origin main
if ($LASTEXITCODE -ne 0) { throw "Git push failed. The local commit is preserved; resolve authentication or network issues and rerun git push origin main." }

Write-Host "Published successfully: https://github.com/Manav326/QuantaEdge-AI-Platform" -ForegroundColor Green
