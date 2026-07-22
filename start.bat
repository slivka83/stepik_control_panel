@echo off
setlocal EnableDelayedExpansion

set PROJECT_DIR=%~dp0

REM Читаем порты из .env
set BACKEND_PORT=8000
set FRONTEND_PORT=3000
for /f "tokens=1,* delims==" %%a in ('findstr /b "BACKEND_PORT=" "%PROJECT_DIR%.env"') do set BACKEND_PORT=%%b
for /f "tokens=1,* delims==" %%a in ('findstr /b "FRONTEND_PORT=" "%PROJECT_DIR%.env"') do set FRONTEND_PORT=%%b

echo.
echo   ┌──────────────────────────────────┐
echo   │      Stepik Control Panel         │
echo   └──────────────────────────────────┘
echo.

REM 1. Docker
echo [1/3] PostgreSQL + Redis...
docker compose -f "%PROJECT_DIR%docker-compose.yml" up -d
timeout /t 3 /nobreak >nul

REM 2. Backend
echo [2/3] Backend (port %BACKEND_PORT%)...
cd /d "%PROJECT_DIR%backend"
if not exist ".venv\Scripts\uvicorn.exe" (
    echo   Creating Python venv...
    uv venv --python 3.12 ".venv"
    if errorlevel 1 (
        echo   ERROR: uv venv failed. Make sure uv is installed: pip install uv
        goto :cleanup
    )
    echo   Installing dependencies...
    uv pip install -r requirements.txt --python ".venv"
    if errorlevel 1 (
        echo   ERROR: uv pip install failed.
        goto :cleanup
    )
)
start /b "" ".venv\Scripts\uvicorn.exe" app.main:app --host 0.0.0.0 --port %BACKEND_PORT% --reload --reload-dir app > "%TEMP%\stepik_backend.log" 2>&1

REM 3. Frontend
echo [3/3] Frontend (port %FRONTEND_PORT%)...
cd /d "%PROJECT_DIR%frontend"
if not exist "node_modules\.bin\vite.cmd" (
    echo   Installing frontend dependencies...
    call npm install
    if errorlevel 1 (
        echo   ERROR: npm install failed. Make sure Node.js is installed.
        goto :cleanup
    )
)
start /b "" node_modules\.bin\vite.cmd --port %FRONTEND_PORT% > "%TEMP%\stepik_frontend.log" 2>&1

timeout /t 5 /nobreak >nul

echo.
echo   ┌──────────────────────────────────┐
echo   │  Open in browser:                 │
echo   │                                  │
echo   │  → http://localhost:%FRONTEND_PORT%
echo   │                                  │
echo   │  API: http://localhost:%BACKEND_PORT%
echo   │                                  │
echo   │  Logs:                           │
echo   │  %TEMP%\stepik_backend.log
echo   │  %TEMP%\stepik_frontend.log
echo   └──────────────────────────────────┘
echo.
echo   Stop: press any key in this window
echo.

pause >nul

:cleanup
echo.
echo   Stopping...
REM Kill by port using PowerShell (locale-independent)
powershell -Command "Get-NetTCPConnection -LocalPort %BACKEND_PORT% -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }" 2>nul
powershell -Command "Get-NetTCPConnection -LocalPort %FRONTEND_PORT% -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }" 2>nul
docker compose -f "%PROJECT_DIR%docker-compose.yml" down >nul 2>&1
echo   Done.
