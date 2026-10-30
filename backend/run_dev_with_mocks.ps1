# run_dev_with_mocks.ps1
# Starts all 3 mock teammate services and the main FastAPI backend in separate PowerShell processes.

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host " Starting Enterprise RAG (Person 1 Lead Dev Environment)" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

$baseDir = $PSScriptRoot
$projectRoot = (Get-Item $baseDir).Parent.FullName

# Explicitly use python 3.11 to avoid Windows py launcher picking unconfigured python versions
$pyExe = "python"

Write-Host "Starting Real Retrieval Server (Port 8002 - Person 3 Engine)..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$projectRoot'; $pyExe -m uvicorn retrieval.api:app --port 8002"

Write-Host "Starting Real Ingestion Server (Port 8003 - Person 2 Pipeline)..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$baseDir'; $pyExe -m uvicorn real_ingestion_server:app --port 8003"

Start-Sleep -Seconds 2

Write-Host "Starting Main Backend Server (Port 8000)..." -ForegroundColor Green
cd $baseDir
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
