#!/usr/bin/env pwsh
# AIS startup script

Write-Host "Astro Intelligence System Startup" -ForegroundColor Cyan
Write-Host "=================================" -ForegroundColor Cyan

Write-Host "`nStarting Docker services (Weaviate, PostgreSQL, Redis)..." -ForegroundColor Yellow
docker-compose up -d
Start-Sleep -Seconds 5

$services = docker-compose ps --format json 2>$null | ConvertFrom-Json
Write-Host "Docker services started" -ForegroundColor Green

$venvPath = ".\backend\.venv"
if (-not (Test-Path $venvPath)) {
    Write-Host "`nCreating Python virtual environment..." -ForegroundColor Yellow
    python -m venv $venvPath
}

& "$venvPath\Scripts\Activate.ps1"

Write-Host "`nInstalling Python dependencies..." -ForegroundColor Yellow
pip install -r .\backend\requirements.txt -q

Write-Host "`nStarting AIS FastAPI server..." -ForegroundColor Green
Write-Host "  API:      http://localhost:8000" -ForegroundColor White
Write-Host "  Frontend: http://localhost:8000/app" -ForegroundColor White
Write-Host "  Docs:     http://localhost:8000/docs" -ForegroundColor White
Write-Host "  Health:   http://localhost:8000/health" -ForegroundColor White
Write-Host ""
Write-Host "  To seed the knowledge base after startup:" -ForegroundColor White
Write-Host "  curl -X POST http://localhost:8000/api/predict/seed" -ForegroundColor White
Write-Host ""

Set-Location .\backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
