<#
.SYNOPSIS
    Starts the full THUTOra / Ai_TUTOR stack: Postgres (Docker), the
    FastAPI backend (uvicorn), and the Vite frontend -- each in its own
    PowerShell window so you can watch all three logs at once.

.NOTES
    Run this from anywhere; it cd's to the project root itself. If your
    project lives somewhere other than the default below, pass it:
        .\start-thutora.ps1 -ProjectRoot "D:\Code\Ai_TUTOR"

    What it does, in order:
      1. Starts the Postgres/pgvector container via `docker compose up -d`
         (Docker Desktop must already be running -- it will NOT launch
         Docker Desktop itself).
      2. Opens a new window, activates backend/.venv, runs
         `alembic upgrade head` (applies the new attachments migration
         if you haven't yet), then starts uvicorn on port 8000.
      3. Opens a second new window and runs `npm run dev` in frontend/.
      4. Opens your default browser to the frontend once it's likely up.

    Stopping: close the two new windows (or Ctrl+C inside each), then
    `docker compose down` in the project root if you want to stop
    Postgres too (left running by default so you don't lose it between
    sessions).
#>

param(
    [string]$ProjectRoot = "C:\Users\SiyaZ\Documents\PROJECTS\Ai_TUTOR"
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path $ProjectRoot)) {
    Write-Error "Project root not found: $ProjectRoot`nPass the right path with -ProjectRoot."
    exit 1
}

Set-Location $ProjectRoot
Write-Host "==> Project root: $ProjectRoot" -ForegroundColor Cyan

# 1. Postgres (pgvector) via Docker -----------------------------------
Write-Host "==> Starting Postgres (docker compose up -d)..." -ForegroundColor Cyan
try {
    docker compose up -d
}
catch {
    Write-Warning "docker compose failed -- is Docker Desktop running? Start it and re-run this script."
    exit 1
}

# 2. Backend (FastAPI/uvicorn) in its own window -----------------------
$backendCommand = @"
Set-Location '$ProjectRoot\backend'
Write-Host '==> Activating venv...' -ForegroundColor Cyan
& '.\.venv\Scripts\Activate.ps1'
Write-Host '==> Installing/updating backend dependencies (pypdf, python-docx, etc.)...' -ForegroundColor Cyan
pip install -r requirements.txt
Write-Host '==> Applying any pending migrations (alembic upgrade head)...' -ForegroundColor Cyan
alembic upgrade head
Write-Host '==> Starting uvicorn on http://localhost:8000 ...' -ForegroundColor Cyan
uvicorn app.main:app --reload --port 8000
"@

Write-Host "==> Opening backend window..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList "-NoExit", "-Command", $backendCommand

# 3. Frontend (Vite) in its own window ----------------------------------
$frontendCommand = @"
Set-Location '$ProjectRoot\frontend'
Write-Host '==> Starting frontend (npm run dev)...' -ForegroundColor Cyan
npm run dev
"@

Write-Host "==> Opening frontend window..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList "-NoExit", "-Command", $frontendCommand

# 4. Open the browser once things have had a moment to come up ---------
Write-Host "==> Giving uvicorn/vite a few seconds to start..." -ForegroundColor Cyan
Start-Sleep -Seconds 6
Start-Process "http://localhost:5173"

Write-Host ""
Write-Host "THUTOra should be starting up in two new windows (backend + frontend)." -ForegroundColor Green
Write-Host "Backend:  http://localhost:8000/health" -ForegroundColor Green
Write-Host "Frontend: http://localhost:5173" -ForegroundColor Green
Write-Host "If the frontend shows a backend-connection error, give uvicorn a few more seconds and refresh." -ForegroundColor Yellow
