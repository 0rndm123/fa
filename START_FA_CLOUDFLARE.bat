@echo off
setlocal EnableExtensions
cd /d "%~dp0"

rem Standalone, named Cloudflare Tunnel for FA_Agent only.
rem Required: a self-hosted Cloudflare Access application protecting the hostname.
rem Never use quick tunnels or reveal access tokens via process command lines.
set "FA_REMOTE_AUTH_MODE=cloudflare_access"

if not defined FA_CF_ACCESS_TEAM_DOMAIN goto :missing
if not defined FA_CF_ACCESS_AUD goto :missing
if not defined FA_TUNNEL_HOSTNAME goto :missing

if not defined FA_TUNNEL_CONFIG set "FA_TUNNEL_CONFIG=%USERPROFILE%\.cloudflared\fa-agent.yml"
if not exist "%FA_TUNNEL_CONFIG%" (
    echo [ERROR] Cloudflare tunnel configuration missing:
    echo   %FA_TUNNEL_CONFIG%
    echo See docs\CLOUDFLARE_TUNNEL.md to configure a dedicated named tunnel.
    exit /b 1
)
where cloudflared.exe >nul 2>&1
if errorlevel 1 (
    echo [ERROR] cloudflared.exe not found on PATH.
    echo Install Cloudflare Tunnel client first. See docs\CLOUDFLARE_TUNNEL.md
    exit /b 1
)

rem Sanity check application configuration before launching another console.
set "PY=python"
if exist ".venv\Scripts\python.exe" set "PY=.venv\Scripts\python.exe"
"%PY%" -c "from fa_agents.cloudflare_access import remote_configuration; remote_configuration(); import jwt; print('Cloudflare Access configuration: OK')" 
if errorlevel 1 (
    echo [ERROR] Invalid Cloudflare Access configuration or missing PyJWT.
    echo Install with: python -m pip install -e ".[dev,web,ai]"
    exit /b 1
)

echo.
echo FA_Agent Cloudflare Access tunnel
echo Remote hostname: %FA_TUNNEL_HOSTNAME%
echo Backend: 127.0.0.1:8300
echo Authentication: signed Cloudflare Access JWT required for ALL endpoints.
echo Local FA_Agent and SysTrd tunnels are independent.
echo.
echo Opening protected FA_Agent backend in a separate console...
start "FA_Agent protected backend" "%ComSpec%" /k call "%~dp0START_FA.bat"
if errorlevel 1 (
    echo [ERROR] Could not start backend console.
    exit /b 1
)
echo Launching named Cloudflare Tunnel (CTRL+C to stop the tunnel)...
echo Ensure the hostname is already restricted in Cloudflare Zero Trust Access.
echo.
cloudflared tunnel --config "%FA_TUNNEL_CONFIG%" run
if errorlevel 1 (
    echo [ERROR] cloudflared tunnel exited with an error.
    echo Check tunnel config and Cloudflare Zero Trust Access policy.
    pause
    exit /b 1
)
exit /b 0

:missing
echo [ERROR] Required environment settings missing.
echo Set FA_CF_ACCESS_TEAM_DOMAIN, FA_CF_ACCESS_AUD and FA_TUNNEL_HOSTNAME.
echo Read docs\CLOUDFLARE_TUNNEL.md before exposing FA_Agent remotely.
exit /b 1
