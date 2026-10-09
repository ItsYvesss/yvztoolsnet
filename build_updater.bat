@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul || (echo Python not found. & pause & exit /b 1)
py -m pip install pyinstaller
py -m PyInstaller --noconfirm --clean --onefile --windowed --name YVZUPDATER --distpath . --icon "yvztools.ico" --version-file version_info.txt updater.py
if errorlevel 1 (echo Build failed.&pause&exit /b 1)
echo SUCCESS: YVZUPDATER.exe
pause
