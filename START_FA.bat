@echo off
setlocal
cd /d "%~dp0"
set "PY=python"
if exist ".venv\Scripts\python.exe" set "PY=.venv\Scripts\python.exe"

echo FA Agent local workbench
echo Working directory: %CD%
echo Browser URL: http://127.0.0.1:8300
echo.

rem Windows User variables may have been set AFTER opening this console.
rem Load the persisted SEC identification if not set in the process.
rem Never print the value or write it to disk.
if not defined SEC_USER_AGENT (
  for /f "usebackq delims=" %%A in (`powershell.exe -NoProfile -NonInteractive -Command "[Environment]::GetEnvironmentVariable('SEC_USER_AGENT','User')"`) do set "SEC_USER_AGENT=%%A"
)
"%PY%" -c "from fa_agents.providers import sec_user_agent_config; v,source=sec_user_agent_config(); print('SEC identification: '+('configured ('+source+')' if v else 'MISSING - financial agents will not run'))"
if errorlevel 1 (
  echo FA Agent Python package could not be loaded. Install with:
  echo python -m pip install -e ".[dev,web,ai]"
  pause
  exit /b 1
)

echo.
echo Press CTRL+C to stop the local server.
echo If port 8300 is already in use, stop the older server before retrying.
echo.
"%PY%" -m uvicorn fa_agents.webapp:app --host 127.0.0.1 --port 8300
if errorlevel 1 (
  echo.
  echo Server did not start. Check whether an older copy is already running on port 8300.
  echo Install missing dependencies with: python -m pip install -e ".[dev,web,ai]"
  pause
  exit /b 1
)
