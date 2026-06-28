@echo off
cd /d "%~dp0"
echo Building executable...
py -m pip install --upgrade pyinstaller customtkinter yt-dlp
py -m PyInstaller --noconfirm --onefile --windowed --name Pullr app.py
if exist "ffmpeg" (
  xcopy /E /I /Y "ffmpeg" "dist\ffmpeg"
)
echo.
echo Build complete. Check the dist folder.
pause
