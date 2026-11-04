@echo off
rem Docker Desktop -> pgvector container -> Streamlit app (opens the browser)
cd /d "%~dp0"

docker info >nul 2>&1
if errorlevel 1 (
  echo Starting Docker Desktop...
  start "" "%LOCALAPPDATA%\Programs\DockerDesktop\Docker Desktop.exe"
  for /l %%i in (1,1,60) do (
    docker info >nul 2>&1
    if errorlevel 1 timeout /t 3 /nobreak >nul
  )
)

docker info >nul 2>&1
if errorlevel 1 (
  echo Docker did not start. Open Docker Desktop yourself and run this file again.
  pause
  exit /b 1
)

echo Starting database...
docker compose up -d db
if errorlevel 1 (
  echo Could not start the database container.
  pause
  exit /b 1
)

echo Starting app... (close this window or press Ctrl+C to stop)
uv run streamlit run app.py
pause
