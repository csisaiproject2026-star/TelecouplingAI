@echo off
chcp 65001 >nul
echo ============================================
echo   CSIS Platform - Starting Local Dev
echo ============================================
echo.

set PROJECT_DIR=%~dp0
set BACKEND_DIR=%PROJECT_DIR%backend
set FRONTEND_DIR=%PROJECT_DIR%frontend

echo [1/3] Starting Backend (FastAPI)...
start "CSIS Backend" cmd /k "cd /d "%BACKEND_DIR%" && conda activate TeleCouplingAI && python main.py"

timeout /t 3 /nobreak >nul

echo [2/3] Starting Celery Worker...
start "CSIS Celery Worker" cmd /k "cd /d "%BACKEND_DIR%" && conda activate TeleCouplingAI && celery -A workers.task_queue worker --loglevel=info -P solo"

timeout /t 2 /nobreak >nul

echo [3/3] Starting Frontend (Vite)...
start "CSIS Frontend" cmd /k "cd /d "%FRONTEND_DIR%" && npm run dev"

echo.
echo ============================================
echo   All services started!
echo   Open browser: http://localhost:5173
echo ============================================
echo.
pause
