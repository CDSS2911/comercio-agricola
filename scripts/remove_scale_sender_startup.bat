@echo off
setlocal

set "STARTUP_DIR=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
set "TARGET=%STARTUP_DIR%\Iniciar Envio de Pesas.bat"

if exist "%TARGET%" (
    del /f /q "%TARGET%"
    echo Inicio automatico eliminado:
    echo %TARGET%
) else (
    echo No habia inicio automatico configurado.
)

echo.
pause
