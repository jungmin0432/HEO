@echo off
setlocal
cd /d "%~dp0.."
".venv\Scripts\python.exe" -m flask --app app:create_app run --host 127.0.0.1 --port 5050
