@echo off
setlocal EnableDelayedExpansion

set PROJECT_DIR=%~dp0

REM Проверка .env
if not exist "%PROJECT_DIR%.env" (
    echo .env file not found. Copy from .env.example and fill in values.
    exit /b 1
)

REM Проверка зависимостей
where docker >nul 2>&1
if errorlevel 1 (
    echo Missing dependency: docker. Please install Docker and try again.
    exit /b 1
)
where node >nul 2>&1
if errorlevel 1 (
    echo Missing dependency: node. Please install Node.js and try again.
    exit /b 1
)
where npm >nul 2>&1
if errorlevel 1 (
    echo Missing dependency: npm. Please install Node.js and try again.
    exit /b 1
)
where uv >nul 2>&1
if errorlevel 1 (
    echo Missing dependency: uv. Please install it: pip install uv
    exit /b 1
)

REM Читаем порты из .env
set BACKEND_PORT=8000
set FRONTEND_PORT=3000
for /f "tokens=1,* delims==" %%a in ('findstr /b "BACKEND_PORT=" "%PROJECT_DIR%.env"') do set BACKEND_PORT=%%b
for /f "tokens=1,* delims==" %%a in ('findstr /b "FRONTEND_PORT=" "%PROJECT_DIR%.env"') do set FRONTEND_PORT=%%b
REM Обрезаем пробелы из значений портов
set BACKEND_PORT=!BACKEND_PORT: =!
set FRONTEND_PORT=!FRONTEND_PORT: =!

echo.
echo   ┌──────────────────────────────────┐
echo   │      Stepik Control Panel         │
echo   └──────────────────────────────────┘
echo.

REM 1. Docker
echo [1/3] PostgreSQL + Redis...
docker compose -f "%PROJECT_DIR%docker-compose.yml" up -d

set /a elapsed=0
:wait_postgres
docker compose -f "%PROJECT_DIR%docker-compose.yml" exec -T postgres pg_isready >nul 2>&1
if not errorlevel 1 goto postgres_ready
set /a elapsed+=1
if !elapsed! geq 30 (
    echo Timeout waiting for PostgreSQL
    goto :cleanup
)
timeout /t 1 /nobreak >nul
goto wait_postgres
:postgres_ready
echo   PostgreSQL is ready

set /a elapsed=0
:wait_redis
docker compose -f "%PROJECT_DIR%docker-compose.yml" exec -T redis redis-cli ping >nul 2>&1
if not errorlevel 1 goto redis_ready
set /a elapsed+=1
if !elapsed! geq 30 (
    echo Timeout waiting for Redis
    goto :cleanup
)
timeout /t 1 /nobreak >nul
goto wait_redis
:redis_ready
echo   Redis is ready

REM 2. Backend
echo [2/3] Backend (port %BACKEND_PORT%)...
cd /d "%PROJECT_DIR%backend"
if not exist ".venv\Scripts\uvicorn.exe" (
    echo   Creating Python venv...
    uv venv --clear --python 3.12 ".venv"
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
REM Kill by port using PowerShell (locale-independent; только процессы-слушатели, чтобы не задеть чужие клиентские соединения)
powershell -Command "Get-NetTCPConnection -LocalPort %BACKEND_PORT% -State Listen -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }" 2>nul
powershell -Command "Get-NetTCPConnection -LocalPort %FRONTEND_PORT% -State Listen -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }" 2>nul
docker compose -f "%PROJECT_DIR%docker-compose.yml" down >nul 2>&1
echo   Done.
