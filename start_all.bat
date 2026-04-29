@echo off
cd /d C:\Users\v\Desktop\trading_bot
start "Trading Bot" cmd /k "call .venv\Scripts\activate && python webhook_bot.py"
timeout /t 2 >nul
start "Ngrok Tunnel" cmd /k "ngrok http 5000"
