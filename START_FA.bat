@echo off
setlocal
cd /d "%~dp0"
set "PY=python"
if exist ".venv\Scripts\python.exe" set "PY=.venv\Scripts\python.exe"
echo Starting FA Agent Research Workbench at http://127.0.0.1:8300
echo Press CTRL+C to stop the local server.
echo.
start "" "http://127.0.0.1:8300"
"%PY%" -m uvicorn fa_agents.webapp:app --host 127.0.0.1 --port 8300
if errorlevel 1 (
  echo.
  echo Check local Python environment and install dependencies:
  echo python -m pip install -e ".[dev,web,ai]"
  pause
)
