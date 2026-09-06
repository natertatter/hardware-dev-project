@echo off
setlocal EnableExtensions

REM ── EDA Platform one-click launcher (Windows) ──────────────────────────
REM Double-click this file to start the API + UI dev servers.
REM Two terminal windows will open (one for each). Close them to stop.

cd /d "%~dp0"

echo.
echo  EDA Platform - Starting...
echo  Project: %CD%
echo.

REM ── Find Python ────────────────────────────────────────────────────────
set "PYTHON=python"
where python >nul 2>&1 || set "PYTHON=py"
where %PYTHON% >nul 2>&1 || (
  echo [ERROR] Python not found. Install from https://www.python.org/downloads/
  echo         Check "Add python.exe to PATH" during install.
  pause
  exit /b 1
)

REM ── Find Node.js ─────────────────────────────────────────────────────────
where node >nul 2>&1 || (
  echo [ERROR] Node.js not found. Install LTS from https://nodejs.org/
  pause
  exit /b 1
)

REM ── Install backend deps if needed ───────────────────────────────────────
%PYTHON% -c "import eda_platform" >nul 2>&1
if errorlevel 1 (
  echo [SETUP] Installing Python dependencies (first run only)...
  %PYTHON% -m pip install -e ".[dev]"
  if errorlevel 1 (
    echo [ERROR] pip install failed.
    pause
    exit /b 1
  )
)

REM ── Install UI deps if needed ────────────────────────────────────────────
if not exist "ui\node_modules\" (
  echo [SETUP] Installing UI dependencies (first run only)...
  pushd ui
  call npm install
  if errorlevel 1 (
    echo [ERROR] npm install failed.
    popd
    pause
    exit /b 1
  )
  popd
)

REM ── Start API server (new window) ────────────────────────────────────────
echo [START] API server on http://localhost:8000
start "EDA Platform - API" cmd /k "cd /d "%CD%" && %PYTHON% -m uvicorn eda_platform.api.main:app --reload --port 8000"

REM Give the API a moment to bind before the UI loads the catalog
timeout /t 3 /nobreak >nul

REM ── Start UI dev server (new window) ─────────────────────────────────────
echo [START] UI on http://localhost:3000
start "EDA Platform - UI" cmd /k "cd /d "%CD%\ui" && set NEXT_PUBLIC_API_URL=http://localhost:8000 && npm run dev"

REM ── Open browser ─────────────────────────────────────────────────────────
timeout /t 5 /nobreak >nul
start "" "http://localhost:3000"

echo.
echo  Done! Two windows opened:
echo    - EDA Platform - API
echo    - EDA Platform - UI
echo.
echo  Browser: http://localhost:3000
echo  API health: http://localhost:8000/health
echo.
echo  Close both terminal windows to stop the app.
echo.
pause
