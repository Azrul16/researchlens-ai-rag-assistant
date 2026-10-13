@echo off
title ResearchLens AI
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo Existing .venv not found. Follow the Windows setup in README.md.
    pause
    exit /b 1
)
".venv\Scripts\python.exe" "scripts\launch.py"
if errorlevel 1 pause
