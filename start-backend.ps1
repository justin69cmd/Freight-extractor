# Native local backend (Windows 11, PowerShell) — SQLite + in-process jobs, no Docker.
$ErrorActionPreference = "Stop"
Set-Location "$PSScriptRoot\backend"

if (-not (Test-Path .venv)) { python -m venv .venv }
& .\.venv\Scripts\Activate.ps1

python -m pip install -q --upgrade pip
pip install -q -r requirements-local.txt
if (-not (Test-Path .env)) { Copy-Item .env.example .env }

python -m scripts.init_db
Write-Host ""
Write-Host "  Backend running  ->  http://localhost:8000   (API docs: /docs)"
Write-Host ""
uvicorn app.main:app --reload --port 8000
