@echo off
chcp 65001 >nul
echo ============================================
echo   CSIS Platform - Local Dev Launcher
echo   (Windows, conda TeleCouplingAI env)
echo ============================================
echo.

set PROJECT_DIR=%~dp0
set BACKEND_DIR=%PROJECT_DIR%backend
set FRONTEND_DIR=%PROJECT_DIR%frontend

REM --- Redis (required by Celery) ---
echo [0/4] Checking Redis...
redis-cli ping >nul 2>&1
if %errorlevel% neq 0 (
    echo   Redis not running. Starting redis-server...
    start "CSIS Redis" cmd /k "redis-server --port 6379"
    timeout /t 2 /nobreak >nul
) else (
    echo   Redis already running.
)

REM --- Backend (FastAPI / uvicorn) ---
echo [1/4] Starting Backend (FastAPI + uvicorn)...
start "CSIS Backend" cmd /k "cd /d "%BACKEND_DIR%" && conda activate TeleCouplingAI && uvicorn main:app --host 0.0.0.0 --port 8000 --reload"

timeout /t 3 /nobreak >nul

REM --- Celery Worker ---
echo [2/4] Starting Celery Worker...
start "CSIS Celery Worker" cmd /k "cd /d "%BACKEND_DIR%" && conda activate TeleCouplingAI && celery -A celery_app worker --loglevel=info -P solo --concurrency=1"

timeout /t 2 /nobreak >nul

REM --- Frontend (Vite dev server) ---
echo [3/4] Starting Frontend (Vite)...
start "CSIS Frontend" cmd /k "cd /d "%FRONTEND_DIR%" && npm run dev"

echo.
echo ============================================
echo   All services started!
echo.
echo   Frontend :  http://localhost:5173
echo   Backend  :  http://localhost:8000
echo   API docs :  http://localhost:8000/docs
echo   Health   :  http://localhost:8000/health
echo.
echo   NOTE: For Docker deployment use:
echo     docker compose --env-file .env.docker up -d
echo ============================================
echo.
pause
