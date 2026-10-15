@echo off
cd /d "%~dp0"
if exist "%~dp0SVCleaner.exe" (
    "%~dp0SVCleaner.exe" %*
    if errorlevel 1 pause
    exit /b
)
python companion\app.py %*
if errorlevel 1 pause
