@echo off
title Day Trading Bot  -  close this window to stop
pushd "%~dp0"
where python >nul 2>nul || (echo Python was not found on your PATH. Install Python 3 and try again. & pause & exit /b 1)
echo ==========================================
echo    DAY TRADING BOT
echo ==========================================
echo.
echo Starting the bot... the dashboard opens in your browser automatically.
echo Keep this window open while the bot runs. Close it to STOP the bot.
echo.
python main.py
echo.
echo The bot has stopped.
pause
