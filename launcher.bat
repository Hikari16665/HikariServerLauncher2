@echo off
title Hikari Server Launcher

echo Starting Hikari Server Launcher...
echo.

:: Start backend
echo [1/2] Starting backend server...
start "HSL Server" /D "%~dp0" "%~dp0\hsl-server\hsl-server.exe"

:: Wait for backend to become ready
echo Waiting for backend to become ready...
:wait_backend
ping -n 2 127.0.0.1 >nul
curl -s http://127.0.0.1:5000/api/ping >nul 2>&1
if %ERRORLEVEL% neq 0 goto wait_backend

:: Start frontend
echo [2/2] Starting frontend...
start "" /D "%~dp0" "%~dp0hsl-app.exe"

echo.
echo Backend running at: http://127.0.0.1:5000
echo IMPORTANT: Do NOT close the console window titled "HSL Server"
echo.

pause