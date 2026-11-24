@echo off
setlocal
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\backup.ps1" -Reason manual
if errorlevel 1 (
    echo.
)
pause
endlocal
