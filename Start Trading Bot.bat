@echo off
title Day Trading Bot  -  close this window to stop
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
  echo Python was not found on your PATH. Install Python 3 and try again.
  pause
  exit /b 1
)

echo ==========================================
echo    DAY TRADING BOT
echo ==========================================
echo.
echo Starting the bot and dashboard...
echo Your browser will open automatically when it's ready (give it ~10s).
echo.
echo   Keep this window open while the bot runs.
echo   Close this window to STOP the bot.
echo.

REM Background helper: waits for the server, then opens the dashboard.
start "Opening dashboard" /min powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0open_dashboard.ps1"

python main.py

echo.
echo The bot has stopped.
pause
