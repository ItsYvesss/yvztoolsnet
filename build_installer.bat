@echo off
setlocal
cd /d "%~dp0"
echo ================================================
echo   YVZTOOLS v4.0 INSTALLER - WINDOWS EXE BUILD
echo ================================================
where python >nul 2>nul || (echo Python not found. Install Python 3.11+ first. & pause & exit /b 1)
python -m pip install -r requirements.txt
if errorlevel 1 (echo Failed to install Python packages.&pause&exit /b 1)
if exist build rmdir /s /q build
if exist YVZTOOLS-INSTALLER.exe del /q YVZTOOLS-INSTALLER.exe
python -m PyInstaller --noconfirm --clean --onefile --windowed --name YVZTOOLS-INSTALLER --distpath . --icon "yvztools.ico" installer.py
if errorlevel 1 (echo Build failed.&pause&exit /b 1)
echo.
echo SUCCESS: YVZTOOLS-INSTALLER.exe
pause
