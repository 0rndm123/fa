"use strict";
(() => {
  const KEY="fa_agent.supabase.session.v1";
  const nativeFetch=window.fetch.bind(window);
  let config=null, session=null,refreshPromise=null, authEnabled=false;
  try {session=JSON.parse(sessionStorage.getItem(KEY)||"null")}catch{session=null}
  const save=s=>{session=s;if(s)sessionStorage.setItem(KEY,JSON.stringify(s));else sessionStorage.removeItem(KEY)};
  async function authRequest(route,body){
    const r=await nativeFetch(config.supabase_url+"/auth/v1/"+route,{
      method:"POST",headers:{"apikey":config.publishable_key,"Content-Type":"application/json"},
      body:JSON.stringify(body)
    });
    if(!r.ok)throw Error("Unable to authenticate with Supabase.");
    return r.json();
  }
  async function token(){
    if(!session?.access_token)return "";
    if((session.expires_at||0)>Date.now()/1000+60)return session.access_token;
    if(!session.refresh_token){save(null);return ""}
    if(!refreshPromise)refreshPromise=authRequest("token?grant_type=refresh_token",{
      refresh_token:session.refresh_token
    }).then(s=>{save({...s,expires_at:Math.floor(Date.now()/1000)+(s.expires_in||3600)});return session.access_token})
      .catch(()=>{save(null);return ""}).finally(()=>refreshPromise=null);
    return refreshPromise;
  }
  window.fetch=async(input,opts={})=>{
    const url=new URL(typeof input==="string"?input:input instanceof URL?input.href:input.url,location.href);
    if(!authEnabled||url.origin!==location.origin||!url.pathname.startsWith("/api/")||url.pathname==="/api/auth/config")
      return nativeFetch(input,opts);
    const headers=new Headers(opts.headers||(input instanceof Request?input.headers:undefined));
    const jwt=await token();
    if(jwt)headers.set("Authorization","Bearer "+jwt);
    return nativeFetch(input,{...opts,headers});
  };
  function showGate(error=""){
    const gate=document.getElementById("faLoginGate");
    const app=document.querySelector(".app");
    if(!gate)return;
    gate.hidden=false;app.hidden=true;
    document.getElementById("faAuthError").textContent=error;
  }
  function hideGate(){
    document.getElementById("faLoginGate").hidden=true;
    document.querySelector(".app").hidden=false;
  }
  async function check(){
    const jwt=await token();
    if(!jwt){showGate();return}
    const r=await window.fetch("/api/auth/me");
    if(!r.ok){save(null);showGate("This account is not authorized for FA_Agent.");return}
    const who=await r.json();
    hideGate();
    document.getElementById("faUserEmail").textContent=who.email||"Account";
    document.getElementById("faLogout").hidden=false;
  }
  document.addEventListener("DOMContentLoaded",async()=>{
    const form=document.getElementById("faLoginForm");
    document.getElementById("faLogout").onclick=()=>{save(null);location.reload()};
    form.onsubmit=async e=>{
      e.preventDefault();
      const button=form.querySelector("button[type=submit]");
      button.disabled=true;
      try{
        const s=await authRequest("token?grant_type=password",{
          email:document.getElementById("faEmail").value.trim(),
          password:document.getElementById("faPassword").value
        });
        if(!s.access_token||!s.refresh_token)throw Error("Incomplete authentication response.");
        save({...s,expires_at:Math.floor(Date.now()/1000)+(s.expires_in||3600)});
        await check();
        if(document.getElementById("faLoginGate").hidden)location.reload();
      }catch{
        showGate("Incorrect credentials or FA_Agent access not authorized.");
      }finally{
        document.getElementById("faPassword").value="";
        button.disabled=false;
      }
    };
    try{
      const r=await nativeFetch("/api/auth/config");
      if(!r.ok)throw Error("Remote authentication is not configured.");
      config=await r.json();
      authEnabled=Boolean(config.enabled);
      if(!authEnabled){hideGate();return}
      await check();
    }catch{showGate("Supabase authentication is not configured or unavailable.")}
  });
})();
