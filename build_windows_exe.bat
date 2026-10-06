@echo off
setlocal
cd /d "%~dp0"
echo ================================================
echo   YVZTOOLS NETMATH SPACE - WINDOWS EXE BUILD
echo ================================================
echo.
where py >nul 2>nul || (echo Python not found. Install Python 3.11+ first. & pause & exit /b 1)
py -m pip install -r requirements.txt
if errorlevel 1 (echo Failed to install Python packages.&pause&exit /b 1)
if exist build rmdir /s /q build
py -m PyInstaller --noconfirm --clean --onefile --windowed --name YVZNETMATH --distpath . --icon "yvztools.ico" --add-data "yvznetmath_core.py;." --add-data "yvztools.ico;." --hidden-import websocket --hidden-import websocket._abnf --hidden-import websocket._core --hidden-import websocket._exceptions --hidden-import websocket._handshake --hidden-import websocket._http --hidden-import websocket._logging --hidden-import websocket._socket --hidden-import websocket._ssl_compat --hidden-import websocket._url --hidden-import websocket._utils --hidden-import requests --collect-submodules websocket yvz_gui.py
if errorlevel 1 (echo Build failed.&pause&exit /b 1)
echo.
echo SUCCESS: YVZNETMATH.exe
echo.
pause
