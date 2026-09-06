@echo off
setlocal EnableExtensions

REM ── EDA Platform launcher (Windows) ────────────────────────────────────
REM   Double-click          → starts API + UI in this one window
REM   start-eda-platform stop → kills servers on ports 8000 and 3000

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

REM ── Start API in background (same window) ────────────────────────────────
echo [API]  http://localhost:8000  (logging to .eda-api.log)
start /b "" %PYTHON% -m uvicorn eda_platform.api.main:app --reload --port 8000 > ".eda-api.log" 2>&1

echo [API]  Waiting for health check...
set /a _api_wait=0
:wait_api
%PYTHON% -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=1)" >nul 2>&1 && goto :api_ready
set /a _api_wait+=1
if %_api_wait% GEQ 20 (
  echo [WARN] API did not respond after 20s. UI will use the built-in parts library.
  goto :api_ready
)
timeout /t 1 /nobreak >nul
goto :wait_api
:api_ready

REM ── Open browser, then run UI in foreground ────────────────────────────
echo [UI]   http://localhost:3000
echo.
echo  Press Ctrl+C to stop. If the API keeps running, use: start-eda-platform.bat stop
echo.

start "" "http://localhost:3000"

pushd ui
set NEXT_PUBLIC_API_URL=http://localhost:8000
call npm run dev
popd

call :cleanup
echo.
echo  Stopped.
pause
exit /b 0

REM ── Stop command ─────────────────────────────────────────────────────────
:stop
echo Stopping servers on ports 8000 and 3000...
call :cleanup
echo Done.
pause
exit /b 0

REM ── Kill processes bound to API/UI ports ─────────────────────────────────
:cleanup
for /f "tokens=5" %%a in ('netstat -ano 2^>nul ^| findstr ":8000" ^| findstr "LISTENING"') do (
  taskkill /PID %%a /F >nul 2>&1
)
for /f "tokens=5" %%a in ('netstat -ano 2^>nul ^| findstr ":3000" ^| findstr "LISTENING"') do (
  taskkill /PID %%a /F >nul 2>&1
)
exit /b 0
