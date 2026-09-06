@echo off
REM Stops dev servers by killing processes on ports 8000 (API) and 3000 (UI).
REM Run this if you closed the windows but ports are still in use.

echo Stopping EDA Platform servers on ports 8000 and 3000...

for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8000" ^| findstr "LISTENING"') do (
  echo Killing PID %%a (port 8000)
  taskkill /PID %%a /F >nul 2>&1
)

for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":3000" ^| findstr "LISTENING"') do (
  echo Killing PID %%a (port 3000)
  taskkill /PID %%a /F >nul 2>&1
)

echo Done.
pause
