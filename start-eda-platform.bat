@echo off
setlocal EnableExtensions

REM ── EDA Platform launcher (Windows) ────────────────────────────────────
REM   Double-click            → starts API + UI in this window
REM   start-eda-platform stop → frees ports 8000, 3000, 3001

cd /d "%~dp0"

if /i "%~1"=="stop" goto :stop

title EDA Platform

echo.
echo  ╔══════════════════════════════════════╗
echo  ║         EDA Platform                 ║
echo  ╚══════════════════════════════════════╝
echo.

REM ── Prerequisites ──────────────────────────────────────────────────────
set "PYTHON=python"
where python >nul 2>&1 || set "PYTHON=py"
where %PYTHON% >nul 2>&1 || (
  echo [ERROR] Python not found. Install from https://www.python.org/downloads/
  pause
  exit /b 1
)
where node >nul 2>&1 || (
  echo [ERROR] Node.js not found. Install LTS from https://nodejs.org/
  pause
  exit /b 1
)

REM ── First-run setup ────────────────────────────────────────────────────
%PYTHON% -c "import eda_platform" >nul 2>&1
if errorlevel 1 (
  echo [SETUP] Installing Python dependencies...
  %PYTHON% -m pip install -e ".[dev]" || (echo [ERROR] pip install failed. & pause & exit /b 1)
)
if not exist "ui\node_modules\" (
  echo [SETUP] Installing UI dependencies...
  pushd ui && call npm install && popd || (echo [ERROR] npm install failed. & pause & exit /b 1)
)

REM ── Free stale servers from a previous run ─────────────────────────────
echo [INIT] Freeing ports 8000, 3000, 3001 if still in use...
call :free_ports

REM ── Start API (separate minimized window — avoids .eda-api.log file locks) ─
set "CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000,http://localhost:3001,http://127.0.0.1:3001"
echo [API]  http://localhost:8000  (logs in the minimized "EDA API" window)
start "EDA API" /min cmd /c "cd /d "%~dp0" && set CORS_ORIGINS=%CORS_ORIGINS% && %PYTHON% -m uvicorn eda_platform.api.main:app --reload --port 8000"

echo [API]  Waiting for health check...
set /a _api_wait=0
:wait_api
%PYTHON% -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2)" >nul 2>&1 && goto :api_ready
set /a _api_wait+=1
if %_api_wait% GEQ 30 (
  echo [ERROR] API did not respond after 30s.
  echo         Close the "EDA API" window for errors, or run: start-eda-platform.bat stop
  echo         Then try again. Auto-Wire requires the API — mock catalog alone is not enough.
  pause
  exit /b 1
)
timeout /t 1 /nobreak >nul
goto :wait_api
:api_ready
echo [API]  Ready.

REM ── UI on fixed port 3000 ───────────────────────────────────────────────
call :free_port 3000
echo [UI]   http://localhost:3000
echo.
echo  Press Ctrl+C to stop the UI. API keeps running in the "EDA API" window.
echo  To stop everything: start-eda-platform.bat stop
echo.

start "" "http://localhost:3000"

pushd ui
set NEXT_PUBLIC_API_URL=http://localhost:8000
set PORT=3000
call npm run dev -- --port 3000
popd

echo.
echo  UI stopped. Close the "EDA API" window or run: start-eda-platform.bat stop
pause
exit /b 0

REM ── Stop command ─────────────────────────────────────────────────────────
:stop
echo Stopping servers on ports 8000, 3000, and 3001...
call :free_ports
echo Done.
pause
exit /b 0

REM ── Kill listeners on dev ports ─────────────────────────────────────────
:free_ports
call :free_port 8000
call :free_port 3000
call :free_port 3001
exit /b 0

:free_port
for /f "tokens=5" %%a in ('netstat -ano 2^>nul ^| findstr ":%~1 " ^| findstr "LISTENING"') do (
  taskkill /PID %%a /F >nul 2>&1
)
exit /b 0
