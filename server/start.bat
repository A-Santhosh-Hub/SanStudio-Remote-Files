@echo off
title SanStudio File Server
REM Always run from this script's folder (needed when started by Task Scheduler / Startup)
cd /d "%~dp0"

echo.
echo  ============================================
echo    SanStudio File Server  -  Starting...
echo  ============================================
echo.

REM Install dependencies only if they are missing
python -c "import flask, waitress" 2>nul || pip install -r requirements.txt --quiet

echo  Server running at  http://localhost:5000
echo  Press Ctrl+C to stop.
echo.
python server.py
pause
