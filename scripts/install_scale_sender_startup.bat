@echo off
setlocal

REM Instala inicio automatico de envio de pesas al iniciar sesion en Windows.
REM Si existe dist\ConfiguradorPesas.exe, lo usa. Si no, usa Python + script.
REM Uso opcional:
REM   install_scale_sender_startup.bat "Nombre de la pesa"

set "CONFIG_NAME=%~1"
set "PROJECT_ROOT=%~dp0.."
set "STARTUP_DIR=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
set "TARGET=%STARTUP_DIR%\Iniciar Envio de Pesas.bat"
set "EXE_PATH=%PROJECT_ROOT%\dist\ConfiguradorPesas.exe"
set "SCRIPT_PATH=%PROJECT_ROOT%\scripts\scale_sender.py"

if not exist "%STARTUP_DIR%" (
    echo ERROR: No existe carpeta Startup: %STARTUP_DIR%
    pause
    exit /b 1
)

if exist "%EXE_PATH%" (
    set "CMD=\"%EXE_PATH%\" --gui --auto-start"
) else (
    where py >nul 2>nul
    if %errorlevel%==0 (
        set "CMD=py -3 \"%SCRIPT_PATH%\" --gui --auto-start"
    ) else (
        set "CMD=python \"%SCRIPT_PATH%\" --gui --auto-start"
    )
)

if not "%CONFIG_NAME%"=="" (
    set "CMD=%CMD% --auto-config-name \"%CONFIG_NAME%\""
)

(
echo @echo off
echo start "" %CMD%
) > "%TARGET%"

echo.
echo ===============================================
echo Inicio automatico instalado en:
echo %TARGET%
echo ===============================================
echo.
pause
