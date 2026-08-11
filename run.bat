@echo off
REM Inicia ScreenMarker creando el entorno virtual la primera vez.
cd /d "%~dp0"

if not exist ".venv" (
    py -3 -m venv .venv
    call .venv\Scripts\python.exe -m pip install --upgrade pip
    call .venv\Scripts\python.exe -m pip install -r requirements.txt
)

start "" .venv\Scripts\pythonw.exe -m screenmarker %*
