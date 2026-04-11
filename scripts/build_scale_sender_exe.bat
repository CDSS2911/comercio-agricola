@echo off
setlocal

REM Compila Configurador de Pesas en un .exe autocontenido.
REM Requiere internet para instalar dependencias la primera vez.

cd /d "%~dp0.."

where py >nul 2>nul
if %errorlevel%==0 (
    py -3 -m pip install --upgrade pip
    py -3 -m pip install pyserial pyinstaller
    py -3 -m PyInstaller --noconfirm --clean --onefile --windowed --name "ConfiguradorPesas" scripts\scale_sender.py
) else (
    python -m pip install --upgrade pip
    python -m pip install pyserial pyinstaller
    python -m PyInstaller --noconfirm --clean --onefile --windowed --name "ConfiguradorPesas" scripts\scale_sender.py
)

echo.
echo ===============================================
echo EXE generado en: dist\ConfiguradorPesas.exe
echo ===============================================
echo.
pause
