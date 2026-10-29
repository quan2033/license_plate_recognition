@echo off
rem Chay he thong nhan dien bien so: mo 2 cua so (backend cong 8000, frontend cong 5173)
cd /d "%~dp0"

start "Backend - cong 8000" cmd /k ".\venv\Scripts\python.exe -m uvicorn backend.app.main:app --reload --port 8000"
start "Frontend - cong 5173" cmd /k "cd /d frontend && npm run dev"

rem Doi vai giay cho server len roi mo trinh duyet
timeout /t 8 /nobreak >nul
start "" http://localhost:5173
