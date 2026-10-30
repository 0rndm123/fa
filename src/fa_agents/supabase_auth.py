"""FA_Agent independent access check using Supabase authentication and a scoped permission RPC."""
import os
import httpx

class AccessDenied(Exception):
    pass

def settings():
    url=os.getenv("FA_SUPABASE_URL","").rstrip("/")
    key=os.getenv("FA_SUPABASE_PUBLISHABLE_KEY","")
    if not url.startswith("https://") or not key:
        raise AccessDenied("Supabase configuration missing.")
    return url,key

async def verify_access(token):
    if not isinstance(token,str) or not 16 <= len(token) <= 8192:
        raise AccessDenied("Invalid session.")
    url,key=settings()
    headers={"apikey":key,"Authorization":"Bearer "+token}
    try:
        async with httpx.AsyncClient(timeout=7) as client:
            user=await client.get(url+"/auth/v1/user",headers=headers)
            role=await client.post(url+"/rest/v1/rpc/fa_agent_current_permission",headers=headers,json={})
        if user.status_code!=200 or role.status_code!=200:
            raise AccessDenied("Session or permission rejected.")
        profile=user.json()
        entries=role.json()
        if not isinstance(entries,list) or len(entries)!=1 or entries[0].get("enabled") is not True:
            raise AccessDenied("FA_Agent access not enabled.")
        if entries[0].get("role") not in {"user","admin"}:
            raise AccessDenied("Invalid role.")
        if not profile.get("id"):
            raise AccessDenied("Invalid user.")
        return {"subject":profile["id"],"email":profile.get("email"),"role":entries[0]["role"]}
    except (httpx.HTTPError,ValueError,KeyError,TypeError) as exc:
        raise AccessDenied("Unable to verify Supabase session.") from exc
