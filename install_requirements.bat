@echo off
cd /d "%~dp0"
echo Installing requirements...
py -m pip install --upgrade pip
py -m pip install -r requirements.txt
echo.
echo Done. You can run run_app.bat now.
pause
