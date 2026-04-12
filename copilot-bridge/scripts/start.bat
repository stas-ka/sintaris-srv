@echo off
REM start.bat — Start Copilot Bridge on Windows
REM Run from the copilot-bridge root directory

cd /d "%~dp0\.."

if not exist ".env" (
    echo No .env file found. Copying .env.example to .env
    copy .env.example .env
)

echo Starting Copilot Bridge...
python src\server.py
