@echo off
setlocal

REM ====== Configura estos valores ======
set "BASE_URL=http://localhost:5000"
set "PESA_ID=1"
set "TOKEN=Cdss_29112002"
set "PORT=COM15"
set "BAUD=9600"
set "TOL=1.0"
set "RESET=1.0"
set "STABLE_COUNT=1"
set "MIN_INTERVAL=0.0"
set "SERIAL_TIMEOUT=0.005"
set "POLL_SLEEP=0.001"

REM ====== Ejecutar script ======
set "PYTHON_EXE=C:\Users\cdss2\AppData\Local\Microsoft\WindowsApps\python3.12.exe"
"%PYTHON_EXE%" "%~dp0scale_sender.py" --base-url "%BASE_URL%" --pesa-id %PESA_ID% --token "%TOKEN%" --port "%PORT%" --baud %BAUD% --tol %TOL% --reset-threshold %RESET% --stable-count %STABLE_COUNT% --min-interval %MIN_INTERVAL% --serial-timeout %SERIAL_TIMEOUT% --poll-sleep %POLL_SLEEP%

pause
