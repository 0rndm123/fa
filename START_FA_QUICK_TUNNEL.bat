@echo off
setlocal EnableExtensions
cd /d "%~dp0"
set "FA_REMOTE_AUTH_MODE=supabase"
set "PY=python"
if exist ".venv\Scripts\python.exe" set "PY=.venv\Scripts\python.exe"
if not defined FA_SUPABASE_URL goto :missing
if not defined FA_SUPABASE_PUBLISHABLE_KEY goto :missing
where cloudflared.exe >nul 2>&1
if errorlevel 1 (
  echo ERROR: cloudflared.exe is not installed or not in PATH.
  exit /b 1
)
"%PY%" -c "from fa_agents.supabase_auth import settings; settings(); import httpx; print('Supabase access configured')"
if errorlevel 1 (
  echo ERROR: Install Python extras, and check your Supabase URL and publishable key.
  echo python -m pip install -e ".[dev,web,ai]"
  exit /b 1
)
echo Starting FA_Agent locally at port 8300 with mandatory Supabase login.
start "FA_Agent Supabase protected API" "%ComSpec%" /k call "%~dp0START_FA.bat"
if errorlevel 1 exit /b 1
echo.
echo Preparing temporary Cloudflare URL (no credit card needed).
echo The URL is public, but all FA_Agent API requests require account authorization.
echo Keep this window open. CTRL+C stops the tunnel.
echo.
cloudflared tunnel --url http://127.0.0.1:8300
exit /b %ERRORLEVEL%
:missing
echo ERROR: Set FA_SUPABASE_URL and FA_SUPABASE_PUBLISHABLE_KEY first.
echo See docs\QUICK_TUNNEL.md
exit /b 1
