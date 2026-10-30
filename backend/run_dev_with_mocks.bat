@echo off
echo ==========================================================
echo  Starting Enterprise RAG (Person 1 Lead Dev Environment)
echo ==========================================================

cd /d "%~dp0"

echo Starting Mock Retrieval Server (Port 8002)...
start "Mock Retrieval Server (Port 8002)" cmd /k py -m uvicorn mock_retrieval_server:app --port 8002

echo Starting Real Ingestion Server (Port 8003 - Person 2 Pipeline)...
start "Real Ingestion Server (Port 8003)" cmd /k py -m uvicorn real_ingestion_server:app --port 8003

timeout /t 2 /nobreak >nul

echo Starting Main Backend Server (Port 8000)...
py -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
