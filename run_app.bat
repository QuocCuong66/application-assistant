@echo off
title AI Application Assistant Launcher
echo ======================================================
echo    AI APPLICATION ASSISTANT - STARTING SYSTEM
echo ======================================================

cd /d "%~dp0"

echo [1/3] Khoi dong Desktop Agent chay ngam...
start "" /b python desktop_agent.py

echo [2/3] Mo trinh duyet Web...
timeout /t 2 >nul
start http://localhost:8000

echo [3/3] Khoi dong Backend Server...
python main.py
