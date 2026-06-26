@echo off
cd /d D:\PlannerAI
"%~dp0.venv\Scripts\python.exe" -m uvicorn main:app --host 0.0.0.0 --port 8000
