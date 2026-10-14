@echo off
cd /d "%~dp0"
python companion\app.py %*
if errorlevel 1 pause
