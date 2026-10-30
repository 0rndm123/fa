# Temporary Cloudflare Quick Tunnel, with Supabase authentication

The FA_Agent and SysTrd remain independent applications. They share only the
existing `portefolio_site` Supabase Auth project. FA_Agent users need their
OWN authorization (`fa_agent`) even when already authorized for SysTrd.

This is a no-card temporary `*.trycloudflare.com` URL. The address itself is
public; **all research, speech, file upload and settings API endpoints are
protected by Supabase Auth and a separate FA_Agent permission lookup**.

## One-time preparation

1. In the existing Supabase project, identify **Project URL** and the
   **publishable key** from Project Settings / API Keys. Never use the
   `service_role` key or database passwords.
2. Have the private database owner apply the FA_Agent scoped authorization
   migration `20261030_shared_fa_agent_access.sql` to the same project.
   The migration is intentionally not present in this public repository.
3. In Supabase Authentication → Users, make sure your email/password account
   already exists. The administrator must authorize it for **FA_Agent** with
   role **admin** separately from any SysTrd permissions. A new FA_Agent
   account does not authorize itself just by signing up.
4. Install `cloudflared` on Windows (no Cloudflare dashboard subscription,
   dedicated hostname or card is needed for this temporary mode).
5. In PowerShell, replace the samples with your REAL URL and publishable key:

```powershell
[Environment]::SetEnvironmentVariable("FA_SUPABASE_URL", "https://YOUR_PROJECT.supabase.co", "User")
[Environment]::SetEnvironmentVariable("FA_SUPABASE_PUBLISHABLE_KEY", "YOUR_PUBLISHABLE_KEY", "User")
```

Close and reopen the terminal. Then:

```powershell
cd "D:\OD\OneDrive\tech\GitHub\rndm123\fa"
git pull origin main
python -m pip install -e ".[dev,web,ai]"
.\START_FA_QUICK_TUNNEL.bat
```

The tunnel window prints a temporary HTTPS link on startup. Open it in the
browser and sign in using your **existing Supabase email/password**.
The Quick Tunnel URL changes after restart. Closing that window stops the
tunnel; close the separate backend window too.

## Security boundaries and limits

- The normal `START_FA.bat` remains local-only and unaffected.
- Quick Tunnel sets `FA_REMOTE_AUTH_MODE=supabase` in the backend process,
  which validates the Supabase session and a specific FA_Agent permission on
  every API call. Without that mode the remote tunnel MUST NOT be started.
- The authentication page and static JS/CSS are public; no protected data,
  reports, credentials or API actions are public.
- Normal users cannot modify shared model settings. Account administration,
  MFA enrollment, quotas and fully isolated user research storage require
  additional implementation and review before issuing invitations to third
  parties. Do not give others access yet.
- History is stored in the browser session, not a shared backend database.
  The initial setup is for **your account only**.
- Cloudflare Quick Tunnel itself provides no authentication and is intended
  for temporary development access; the application enforces Supabase login.
- No sysTrd imports, database connections, service role keys, or remote
  action permissions are added to this repository.

## Tests

```powershell
python -m pytest -q tests/test_supabase_quick_tunnel.py
python -m pytest -q
```

Do not consider the login operational until the private SQL migration is
applied and a live browser login and rejected-login test have passed. Never
paste the Supabase password or secret keys into ChatGPT or the repository.
