$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
if (-not (Test-Path "$root\.env")) { throw "Missing .env. Run .\scripts\initialize.ps1 first." }
$env:PYTHONPATH = "$root\apps\api"
& "$root\.venv\Scripts\python.exe" -m alembic -c "$root\apps\api\alembic.ini" upgrade head
if ($LASTEXITCODE -ne 0) { throw "Database migration failed." }
