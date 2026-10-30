@echo off
echo ==========================================================
echo  Starting Enterprise RAG (Person 1 Lead Dev Environment)
echo ==========================================================

cd /d "%~dp0"

echo Starting Real Retrieval Server (Port 8002 - Person 3 Engine)...
start "Real Retrieval Server (Port 8002)" cmd /k "cd /d "%~dp0\.." && python -m uvicorn retrieval.api:app --port 8002"

echo Starting Real Ingestion Server (Port 8003 - Person 2 Pipeline)...
start "Real Ingestion Server (Port 8003)" cmd /k python -m uvicorn real_ingestion_server:app --port 8003

timeout /t 2 /nobreak >nul

echo Starting Main Backend Server (Port 8000)...
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
