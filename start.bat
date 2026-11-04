@echo off
rem Docker Desktop -> pgvector DB -> Streamlit app (opens the browser by itself)
cd /d "%~dp0"

docker info >nul 2>&1 && goto up
echo Starting Docker Desktop...
start "" "%LOCALAPPDATA%\Programs\DockerDesktop\Docker Desktop.exe"
set n=0
:wait
set /a n+=1
if %n% gtr 60 (echo Docker did not start within 3 minutes. & pause & exit /b 1)
timeout /t 3 /nobreak >nul
docker info >nul 2>&1 || goto wait

:up
docker compose up -d db || (echo Failed to start the DB container. & pause & exit /b 1)
echo Starting app... close this window to stop it.
uv run streamlit run app.py --server.headless false
pause
