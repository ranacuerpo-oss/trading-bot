@echo off
set TASK_NAME=TradingBot24x7
set SCRIPT_PATH=C:\Users\v\Desktop\trading_bot\start_all.bat

schtasks /Delete /TN "%TASK_NAME%" /F >nul 2>&1
schtasks /Create /SC ONLOGON /TN "%TASK_NAME%" /TR "\"%SCRIPT_PATH%\"" /RL HIGHEST /F

echo.
echo Task "%TASK_NAME%" creada para iniciar al hacer login.
echo Si quieres validar: schtasks /Query /TN "%TASK_NAME%" /V /FO LIST
pause
