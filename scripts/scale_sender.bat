@echo off
setlocal

REM Ejecuta la interfaz grafica del configurador de pesas.
REM Si quieres modo consola, usa scale_sender.py con argumentos.

where py >nul 2>nul
if %errorlevel%==0 (
    py -3 "%~dp0scale_sender.py" --gui
) else (
    python "%~dp0scale_sender.py" --gui
)

pause
