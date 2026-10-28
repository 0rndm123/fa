"use strict";
const $=id=>document.getElementById(id);
const state={report:null,activeTab:"overview",selectedAgents:null,uploadId:null,capabilities:null,running:false,metric:"revenue",messages:[],cotMarketCode:null,cotReportType:null,cotForceAgents:false};
const workspace=$("workspace"),NS="http://www.w3.org/2000/svg";
function el(tag,cls="",value){const n=document.createElement(tag);if(cls)n.className=cls;if(value!==undefined&&value!==null)n.textContent=String(value);return n}
function append(parent,...nodes){nodes.forEach(n=>parent.appendChild(n));return parent}
function clear(n){n.replaceChildren();return n}
function fmt(v){if(v===null||v===undefined)return "—";return typeof v==="number"?new Intl.NumberFormat("en-US",{maximumFractionDigits:3}).format(v):String(v)}
function title(n,x){n.appendChild(el("h2","section-title",x))}
function paragraph(n,x,cls="muted-note"){n.appendChild(el("p",cls,x))}
function badge(status){return el("span","badge "+status,String(status).replaceAll("_"," "))}
function valueRow(k,v){const n=el("div","kpi");n.appendChild(el("label","",k.replaceAll("_"," ")));n.appendChild(el("strong","",fmt(v)));return n}
function section(name){const n=el("section","data-box");n.appendChild(el("h3","",name));return n}
function table(head,rows){const w=el("div","table-wrap"),t=el("table"),h=el("thead"),r=el("tr"),b=el("tbody");head.forEach(s=>r.appendChild(el("th","",s)));h.appendChild(r);t.appendChild(h);rows.forEach(row=>{const line=el("tr");row.forEach(c=>line.appendChild(el("td","",fmt(c))));b.appendChild(line)});t.appendChild(b);w.appendChild(t);return w}
function showError(x){$("warning").textContent=x;$("warning").classList.remove("hidden")}
function hideError(){$("warning").classList.add("hidden");$("warning").textContent=""}
function saveChat(){try{sessionStorage.setItem("fa-chat-session-v1",JSON.stringify(state.messages.slice(-40)))}catch{}}
function conversationScope(){return $("assetClass").value+"|"+$("symbol").value.trim().toUpperCase()}
function drawMessage(role,content,save=true){const n=el("div","message "+role);n.appendChild(el("span","message-role",role==="user"?"YOU":"FA AGENT"));n.appendChild(el("p","",content));$("messages").appendChild(n);$("messages").scrollTop=$("messages").scrollHeight;if(save){state.messages.push({role,content,scope:conversationScope()});saveChat()}}
function restoreHistory(){try{const x=JSON.parse(sessionStorage.getItem("fa-chat-session-v1")||"[]");if(Array.isArray(x))state.messages=x.slice(-40).filter(v=>v&&["user","assistant"].includes(v.role)&&typeof v.content==="string")}catch{}if(state.messages.length){clear($("messages"));state.messages.forEach(x=>drawMessage(x.role,x.content,false))}}
function toggleChat(mode){const mini=workspace.classList.contains("chat-minimized"),maxi=workspace.classList.contains("chat-maximized");workspace.classList.remove("chat-minimized","chat-maximized");if(mode==="min"&&!mini)workspace.classList.add("chat-minimized");if(mode==="max"&&!maxi)workspace.classList.add("chat-maximized");$("chatMaximize").textContent=workspace.classList.contains("chat-maximized")?"⇲":"⛶";$("chatMaximize").title=workspace.classList.contains("chat-maximized")?"Restore split view":"Maximize chat"}
$("chatMinimize").onclick=()=>toggleChat("min");$("chatMaximize").onclick=()=>toggleChat("max");$("chatExpandRail").onclick=()=>toggleChat("min");
(function(){const handle=$("resizeHandle");handle.addEventListener("pointerdown",event=>{if(window.innerWidth<800||workspace.classList.contains("chat-minimized")||workspace.classList.contains("chat-maximized"))return;event.preventDefault();handle.setPointerCapture(event.pointerId);const move=e=>{const bound=workspace.getBoundingClientRect();workspace.style.setProperty("--chat-size",Math.max(270,Math.min(bound.width*.65,e.clientX-bound.left))+"px")};const stop=()=>{handle.removeEventListener("pointermove",move);handle.removeEventListener("pointerup",stop);handle.removeEventListener("pointercancel",stop)};handle.addEventListener("pointermove",move);handle.addEventListener("pointerup",stop);handle.addEventListener("pointercancel",stop)})})();
function agentCount(){$("agentCount").textContent=state.selectedAgents===null?"Auto":state.selectedAgents.length+" selected"}
async function loadCapabilities(){try{const r=await fetch("/api/capabilities",{cache:"no-store"});if(!r.ok)throw Error("Server unavailable");state.capabilities=await r.json();const list=clear($("agentChoices"));state.capabilities.agents.forEach(a=>{const l=el("label"),input=el("input");input.type="checkbox";input.value=a.id;input.onchange=()=>{state.selectedAgents=[...list.querySelectorAll("input:checked")].map(x=>x.value);agentCount()};const text=el("span","",a.id.replaceAll("_"," "));text.title=a.description+" ("+a.implementation+")";if(a.implementation==="planned")text.style.color="#72879c";append(l,input,text);list.appendChild(l)});$("useLLM").disabled=!state.capabilities.llm_configured||$("mode").value==="demo";$("useLLM").title=state.capabilities.llm_configured?"Optional AI commentary":"Set OPENAI_API_KEY_Demo or OPENAI_API_KEY";$("voiceToggle").disabled=!state.capabilities.voice_transcription_configured; if(!state.capabilities.voice_transcription_configured)voiceStatus("Voice transcription unavailable: configure OPENAI_API_KEY_Demo or OPENAI_API_KEY and install [ai].");syncSpeechControls();$("connectionStatus").textContent=(state.capabilities.llm_configured?"AI ready":"AI key unavailable")+" · "+(state.capabilities.sec_configured?"SEC ready":"SEC identity not configured")}catch(err){$("connectionStatus").textContent="Server error";showError(String(err.message))}}
$("agentToggle").onclick=()=>$("agentPanel").classList.toggle("hidden");
$("allAgents").onclick=()=>{const nodes=[...$("agentChoices").querySelectorAll("input")];nodes.forEach(x=>x.checked=true);state.selectedAgents=nodes.map(x=>x.value);agentCount()};
$("clearAgents").onclick=()=>{$("agentChoices").querySelectorAll("input").forEach(x=>x.checked=false);state.selectedAgents=[];agentCount()};
$("defaultAgents").onclick=()=>{$("agentChoices").querySelectorAll("input").forEach(x=>x.checked=false);state.selectedAgents=null;agentCount()};
$("mode").onchange=()=>{const demo=$("mode").value==="demo";$("symbol").disabled=demo;if(demo){$("symbol").value="DEMO";$("useLLM").checked=false}else if($("symbol").value==="DEMO")$("symbol").value="NVDA";$("useLLM").disabled=demo||!(state.capabilities&&state.capabilities.llm_configured);if(demo)showError("DEMO MODE: company figures and news are synthetic.");else hideError()};
$("mode").dispatchEvent(new Event("change"));
$("priceUpload").onchange=async event=>{const file=event.target.files[0];if(!file)return;$("uploadLabel").textContent="Uploading "+file.name+"…";try{const form=new FormData();form.append("file",file);const r=await fetch("/api/upload-prices",{method:"POST",body:form});const data=await r.json();if(!r.ok)throw Error(data.detail||"CSV rejected");state.uploadId=data.upload_id;$("uploadLabel").textContent=file.name+" ("+data.observations+" rows)";hideError()}catch(err){state.uploadId=null;$("uploadLabel").textContent="Upload failed";showError(String(err.message))}};
$("clearChat").onclick=()=>{stopSpeech();lastSpokenAnswer="";syncSpeechControls();state.messages=[];saveChat();clear($("messages"));drawMessage("assistant","Conversation cleared. Start a new research question.")};
async function submitQuery(event){event.preventDefault();if(state.running||voiceBusy||voiceRecorder?.state==="recording")return;stopSpeech();const q=$("question").value.trim();if(!q)return;const history=state.messages.filter(x=>x.scope===conversationScope()).slice(-8).map(x=>({role:x.role,content:x.content.slice(0,2000)}));drawMessage("user",q);$("question").value="";$("emptyState").classList.add("hidden");$("busy").classList.remove("hidden");$("submit").disabled=true;state.running=true;hideError();$("reportBadge").textContent="RUNNING";const payload={symbol:$("symbol").value.trim().toUpperCase(),asset_class:$("assetClass").value,mode:$("mode").value,question:q,horizon:$("horizon").value,agents:state.cotForceAgents?["cot"]:state.selectedAgents,llm:$("useLLM").checked,price_upload_id:state.uploadId,history,cot_market_code:state.cotMarketCode,cot_report_type:state.cotReportType};state.cotMarketCode=null;state.cotReportType=null;state.cotForceAgents=false;try{const response=await fetch("/api/analyze",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(payload)});const data=await response.json();if(!response.ok)throw Error(typeof data.detail==="string"?data.detail:JSON.stringify(data.detail));state.report=data.report;drawMessage("assistant",data.answer);lastSpokenAnswer=typeof data.answer==="string"?data.answer:"";syncSpeechControls();renderReport();if($("autoSpeak").checked)void speakLatestAnswer();if(workspace.classList.contains("chat-maximized"))toggleChat("max")}catch(err){const msg="Research failed: "+String(err.message||err);drawMessage("assistant",msg);showError(msg);$("reportBadge").textContent="ERROR"}finally{$("busy").classList.add("hidden");$("submit").disabled=false;state.running=false}}
$("chatForm").onsubmit=submitQuery;
$("question").onkeydown=event=>{if(event.key==="Enter"&&!event.shiftKey){event.preventDefault();$("chatForm").requestSubmit()}};

// Explicit push-to-record voice input. Audio is never stored in chat history.
let voiceRecorder=null,voiceStream=null,voiceTimeout=null,voiceBusy=false,voiceCancelled=false;
function voiceStatus(text){$("voiceStatus").textContent=text}
function voiceButton(recording){
  const button=$("voiceToggle");
  button.classList.toggle("recording",recording);
  button.setAttribute("aria-pressed",String(recording));
  button.setAttribute("aria-label",recording?"Stop voice recording":"Start voice recording");
  button.textContent=recording?"■ Stop recording":"🎙 Voice";
}
function releaseVoiceStream(){
  if(voiceTimeout!==null){clearTimeout(voiceTimeout);voiceTimeout=null}
  if(voiceStream){voiceStream.getTracks().forEach(track=>track.stop());voiceStream=null}
}
function stopVoiceRecording(){
  if(!voiceRecorder||voiceRecorder.state!=="recording")return;
  voiceBusy=true;
  $("voiceToggle").disabled=true;
  voiceButton(false);
  voiceStatus("Transcribing recording…");
  voiceRecorder.stop();
}
async function sendVoiceRecording(parts,mime){
  const blob=new Blob(parts,{type:mime});
  if(!blob.size)throw Error("No audio was recorded.");
  if(blob.size>10*1024*1024)throw Error("Recording is too large (10 MB maximum).");
  const form=new FormData();
  const ext=mime.startsWith("audio/mp4")?".mp4":mime.startsWith("audio/ogg")?".ogg":".webm";
  form.append("file",blob,"voice"+ext);
  const response=await fetch("/api/transcribe-audio",{method:"POST",body:form});
  const data=await response.json();
  if(!response.ok)throw Error(typeof data.detail==="string"?data.detail:"Transcription failed.");
  if(!data.text||typeof data.text!=="string")throw Error("No speech was detected.");
  const old=$("question").value.trim();
  $("question").value=(old?old+"\n":"")+data.text.trim();
  $("question").focus();
  voiceStatus("Transcription added to the question. Review and click Run analysis.");
}
async function toggleVoice(){
  if(voiceRecorder?.state==="recording"){stopVoiceRecording();return}
  stopSpeech();
  if(voiceBusy||state.running)return;
  if(!navigator.mediaDevices?.getUserMedia||typeof MediaRecorder==="undefined"){
    voiceStatus("This browser does not support microphone recording. Use keyboard dictation instead.");
    return;
  }
  const types=["audio/webm;codecs=opus","audio/mp4","audio/ogg;codecs=opus","audio/webm","audio/ogg"];
  const mime=types.find(t=>MediaRecorder.isTypeSupported(t));
  voiceBusy=true;
  $("voiceToggle").disabled=true;
  voiceStatus("Requesting microphone permission…");
  try{
    voiceStream=await navigator.mediaDevices.getUserMedia({audio:true,video:false});
    voiceCancelled=false;
    const options=mime?{mimeType:mime}:undefined;
    const recorder=new MediaRecorder(voiceStream,options);
    voiceRecorder=recorder;
    const chunks=[];
    recorder.ondataavailable=event=>{if(event.data?.size)chunks.push(event.data)};
    recorder.onerror=()=>{voiceCancelled=true;voiceStatus("Recording failed. Please try again.")};
    recorder.onstop=async()=>{
      const cancelled=voiceCancelled;
      const format=recorder.mimeType||mime||"audio/webm";
      releaseVoiceStream();
      voiceRecorder=null;
      if(cancelled){voiceBusy=false;$("voiceToggle").disabled=false;$("submit").disabled=state.running;voiceButton(false);return}
      try{await sendVoiceRecording(chunks,format)}
      catch(err){voiceStatus("Voice error: "+String(err.message||err))}
      finally{voiceBusy=false;$("voiceToggle").disabled=false;$("submit").disabled=state.running;voiceButton(false)}
    };
    recorder.start(1000);
    voiceBusy=false;
    $("voiceToggle").disabled=false;
    voiceButton(true);
    $("submit").disabled=true;
    voiceStatus("Recording… click Stop recording to transcribe (90 s maximum).");
    voiceTimeout=setTimeout(stopVoiceRecording,90000);
  }catch(err){
    releaseVoiceStream();
    voiceRecorder=null;
    voiceBusy=false;
    $("voiceToggle").disabled=false;
    voiceButton(false);
    $("submit").disabled=state.running;
    voiceStatus("Microphone unavailable or permission denied. Check browser permissions.");
  }
}
$("voiceToggle").onclick=toggleVoice;

// Spoken answers are opt-in. Keep the microphone off during audio playback.
// Abort in-flight synthesis on Stop and revoke all temporary audio URLs.
let lastSpokenAnswer="",speechPlayer=null,speechUrl=null,speechRequest=null,speechGeneration=0;
function syncSpeechControls(){
  const available=Boolean(state.capabilities?.voice_replies_configured);
  $("speakReply").disabled=!available||(!lastSpokenAnswer&&!speechRequest&&!speechPlayer);
  $("autoSpeak").disabled=!available;
  if(!available)$("autoSpeak").checked=false;
}
function stopSpeech(){
  speechGeneration++;
  if(speechRequest){speechRequest.abort();speechRequest=null}
  if(speechPlayer){speechPlayer.pause();speechPlayer.removeAttribute("src");speechPlayer.load();speechPlayer=null}
  if(speechUrl){URL.revokeObjectURL(speechUrl);speechUrl=null}
  $("speakReply").textContent="▶ Listen";
  $("speakReply").setAttribute("aria-label","Read the last answer aloud");
  syncSpeechControls();
}
async function speakLatestAnswer(){
  if(speechRequest||speechPlayer){stopSpeech();return}
  if(!lastSpokenAnswer||!state.capabilities?.voice_replies_configured)return;
  const answer=lastSpokenAnswer.slice(0,2200);
  const isTruncated=lastSpokenAnswer.length>2200;
  speechRequest=new AbortController();
  const generation=++speechGeneration;
  $("speakReply").textContent="■ Stop audio";
  $("speakReply").setAttribute("aria-label","Stop spoken answer");
  $("speakReply").disabled=false;
  voiceStatus("Generating spoken answer…"+(isTruncated?" (first 2200 characters)":""));
  try{
    const response=await fetch("/api/speak-reply",{
      method:"POST",headers:{"Content-Type":"application/json"},
      body:JSON.stringify({text:answer}),signal:speechRequest.signal
    });
    if(!response.ok){
      const error=await response.json().catch(()=>({}));
      throw Error(typeof error.detail==="string"?error.detail:"Spoken answer unavailable");
    }
    const audio=await response.blob();
    if(generation!==speechGeneration)return;
    if(audio.size===0||audio.size>5*1024*1024)throw Error("Invalid spoken audio size");
    speechRequest=null;
    speechUrl=URL.createObjectURL(audio);
    speechPlayer=new Audio(speechUrl);
    speechPlayer.onended=()=>{if(generation===speechGeneration){stopSpeech();voiceStatus("Spoken answer finished.")}};
    speechPlayer.onerror=()=>{if(generation===speechGeneration){stopSpeech();voiceStatus("Audio playback failed.")}};
    await speechPlayer.play();
    if(generation===speechGeneration)voiceStatus("Playing spoken answer. Click Stop audio to interrupt.");
  }catch(error){
    if(generation!==speechGeneration)return;
    stopSpeech();
    if(error.name!=="AbortError")voiceStatus("Spoken answer: "+String(error.message||error));
  }
}
$("speakReply").onclick=()=>{void speakLatestAnswer()};
$("autoSpeak").onchange=()=>{
  if(!$("autoSpeak").checked&&speechRequest){stopSpeech();voiceStatus("Automatic spoken replies disabled.")}
};
["symbol","assetClass"].forEach(id=>$(id).addEventListener("change",()=>{
  stopSpeech();lastSpokenAnswer="";syncSpeechControls();
}));

window.addEventListener("pagehide",()=>{
  voiceCancelled=true;
  if(voiceRecorder?.state==="recording")voiceRecorder.stop();
  releaseVoiceStream();
});

function agents(){return state.report?.results||[]}
function agent(id){return agents().find(x=>x.agent_id===id)||null}
function sources(){const seen=new Set(),items=[];agents().forEach(a=>(a.evidence||[]).forEach(e=>{const key=e.source_id+"|"+e.source_url;if(seen.has(key))return;seen.add(key);items.push({...e,agent:a.agent_id})}));return items}
function renderReport(){const r=state.report;if(!r)return;$("downloadReport").disabled=false;$("resultTitle").textContent=r.request.symbol+" · Research analysis";$("resultSubtitle").textContent=(r.data_mode==="demo"?"SYNTHETIC DEMO":"Live research")+" · "+r.generated_at.slice(0,19).replace("T"," ")+" UTC · "+agents().length+" specialists";$("reportBadge").textContent=r.status.toUpperCase().replaceAll("_"," ");$("reportBadge").className="status-pill "+(r.status==="completed"?"good":r.status==="partial"?"warn":"");if(r.warnings?.length)showError(r.warnings.join("\n"));else hideError();$("emptyState").classList.add("hidden");$("reportArea").classList.remove("hidden");const tabs=[...(r.market_quote?[["quote","Quote"]]:[]),...(agent("cot")?[["cot","COT"]]:[]),...(agent("crypto_derivatives")?[["crypto","Crypto Derivatives"]]:[]),["overview","Overview"],...(agent("financial_data")?.observations?.length||agent("fundamental")?.metrics?[["financial","Financials"]]:[]),...(agent("technical")?[["technical","Technical"]]:[]),
    ...(agent("debt_liquidity")?[["debt","Debt & Liquidity"]]:[]),
    ...(agent("governance")?[["governance","Governance"]]:[]),
    ...(agent("competition")||agent("industry_context")?[["sector","Sector & Peers"]]:[]),...(sources().length?[["sources","Sources"]]:[]),["agents","Specialists"],["json","JSON"]];state.tabs=tabs;if(r.market_quote)state.activeTab="quote";else if(agent("cot"))state.activeTab="cot";else if(agent("crypto_derivatives"))state.activeTab="crypto";else if(!tabs.some(x=>x[0]===state.activeTab))state.activeTab="overview";const nav=clear($("tabs"));tabs.forEach(([id,text])=>{const n=el("button","tab",text);n.type="button";n.setAttribute("role","tab");n.dataset.id=id;n.onclick=()=>{state.activeTab=id;renderTab()};nav.appendChild(n)});renderTab()}
function renderTab(){for(const node of $("tabs").children)node.setAttribute("aria-selected",node.dataset.id===state.activeTab?"true":"false");const parent=clear($("tabContent"));switch(state.activeTab){case"quote":renderQuote(parent);break;case"cot":renderCot(parent);break;case"crypto":renderCryptoDerivatives(parent);break;case"overview":renderOverview(parent);break;case"financial":renderFinancial(parent);break;case"technical":renderTechnical(parent);break;case"debt":renderSpecialistTopic(parent,["debt_liquidity"]);break;case"governance":renderSpecialistTopic(parent,["governance"]);break;case"sector":renderSpecialistTopic(parent,["industry_context","competition"]);break;case"sources":renderSources(parent);break;case"agents":renderAgents(parent);break;case"json":renderJSON(parent);break}}
function renderOverview(parent){const lead=el("section","report-lead");lead.appendChild(el("h3","","Research summary"));paragraph(lead,state.report.summary,"");parent.appendChild(lead);if(state.report.llm_commentary){title(parent,"AI evidence commentary");const b=el("section","report-lead");paragraph(b,state.report.llm_commentary,"");parent.appendChild(b)}title(parent,"Research coverage");const counts={completed:0,partial:0,no_data:0,failed:0,not_implemented:0};agents().forEach(x=>counts[x.status]=(counts[x.status]||0)+1);const grid=el("div","kpi-grid");append(grid,valueRow("Completed",counts.completed),valueRow("Partial",counts.partial),valueRow("Unavailable",counts.no_data+counts.failed+counts.not_implemented),valueRow("Source records",sources().length));parent.appendChild(grid);const metrics=agent("financial_performance")?.metrics||agent("fundamental")?.metrics||agent("financial_data")?.metrics;if(metrics){title(parent,"Key financial metrics");const g=el("div","kpi-grid");["revenue_usd","annual_revenue_growth_pct","net_margin_pct","fcf_proxy_usd"].forEach(k=>{if(metrics[k]!==undefined)g.appendChild(valueRow(k,metrics[k]))});if(g.childElementCount)parent.appendChild(g)}title(parent,"Specialist outcomes");parent.appendChild(table(["Specialist","Status","Summary"],agents().map(x=>[x.agent_id,x.status,x.summary||x.limitations?.[0]||"—"])));if(state.report.warnings?.length){title(parent,"Warnings");const box=section("Coverage limits"),ul=el("ul");state.report.warnings.forEach(x=>ul.appendChild(el("li","",x)));box.appendChild(ul);parent.appendChild(box)}}
function compact(v){const abs=Math.abs(v);if(abs>=1e9)return(v/1e9).toFixed(1)+"B";if(abs>=1e6)return(v/1e6).toFixed(1)+"M";if(abs>=1e3)return(v/1e3).toFixed(1)+"K";return v.toFixed(1)}
function drawLineChart(points){const svg=document.createElementNS(NS,"svg");svg.setAttribute("viewBox","0 0 700 250");svg.setAttribute("class","chart");svg.setAttribute("role","img");svg.setAttribute("aria-label","Numeric time series");const values=points.map(p=>Number(p.y));if(!points.length||values.some(x=>!Number.isFinite(x)))return el("div","empty-chart","No numeric history");const L=78,R=678,T=22,B=207;let lo=Math.min(...values),hi=Math.max(...values);if(lo===hi){lo-=Math.max(1,Math.abs(lo)*.1);hi+=Math.max(1,Math.abs(hi)*.1)}const pad=(hi-lo)*.08;lo-=pad;hi+=pad;const X=i=>L+(points.length===1?.5:i/(points.length-1))*(R-L),Y=v=>B-(v-lo)/(hi-lo)*(B-T);const line=(a,b,c,d)=>{const n=document.createElementNS(NS,"line");Object.entries({x1:a,y1:b,x2:c,y2:d}).forEach(([key,v])=>n.setAttribute(key,String(v)));svg.appendChild(n)};const text=(x,y,s,anchor="start")=>{const n=document.createElementNS(NS,"text");n.setAttribute("x",x);n.setAttribute("y",y);n.setAttribute("text-anchor",anchor);n.textContent=s;svg.appendChild(n)};for(let i=0;i<=4;i++){const y=T+i*(B-T)/4;line(L,y,R,y);text(L-9,y+3,compact(hi-i*(hi-lo)/4),"end")}text(L,B+24,points[0].x);if(points.length>1)text(R,B+24,points[points.length-1].x,"end");const poly=document.createElementNS(NS,"polyline");poly.setAttribute("points",points.map((p,i)=>X(i).toFixed(1)+","+Y(Number(p.y)).toFixed(1)).join(" "));svg.appendChild(poly);if(points.length<=24)points.forEach((p,i)=>{const c=document.createElementNS(NS,"circle");c.setAttribute("cx",X(i));c.setAttribute("cy",Y(Number(p.y)));c.setAttribute("r",3.5);c.setAttribute("fill","#a8d6ff");svg.appendChild(c)});return svg}
function renderFinancial(parent){const data=agent("financial_data"),fund=agent("fundamental")||agent("financial_performance"),observations=(data?.observations||[]).filter(x=>Number.isFinite(x.value));if(observations.length){const metrics=[...new Set(observations.map(x=>x.metric))];if(!metrics.includes(state.metric))state.metric=metrics[0];const box=section("Financial history · annual SEC 10-K");const bar=el("div","metric-toolbar");bar.appendChild(el("label","","Metric"));const select=el("select");metrics.forEach(m=>{const o=el("option","",m.replaceAll("_"," "));o.value=m;o.selected=m===state.metric;select.appendChild(o)});select.onchange=()=>{state.metric=select.value;renderTab()};bar.appendChild(select);box.appendChild(bar);const series=observations.filter(x=>x.metric===state.metric).sort((a,b)=>a.period_end.localeCompare(b.period_end));box.appendChild(drawLineChart(series.map(x=>({x:x.period_end,y:x.value}))));paragraph(box,"USD · Original filed values; definitions and fiscal years may differ.");parent.appendChild(box);title(parent,"Annual data table");const years=[...new Set(observations.map(x=>x.period_end))].sort(),map=new Map(observations.map(x=>[x.metric+"|"+x.period_end,x.value]));parent.appendChild(table(["Metric",...years],metrics.map(m=>[m.replaceAll("_"," "),...years.map(y=>map.get(m+"|"+y)??"—")])))}else paragraph(parent,"No financial history available.");if(fund){title(parent,"Fundamental calculations");parent.appendChild(table(["Metric","Value"],Object.entries(fund.metrics||{})));const box=section("Derived observations"),list=el("ul");(fund.claims||[]).forEach(x=>list.appendChild(el("li","",x)));box.appendChild(list);parent.appendChild(box)}}
function renderTechnical(parent){const a=agent("technical");if(!a)return;const m=a.metrics||{},grid=el("div","kpi-grid");["last_close","last_return_pct","sma20","sma50","sma200","sma20_1h","sma50_1h","rsi14_simple","observations"].forEach(k=>{if(m[k]!==undefined)grid.appendChild(valueRow(k,m[k]))});if(grid.childElementCount)parent.appendChild(grid);const box=section("Daily closing price"),points=(a.observations||[]).filter(x=>x.metric==="close").map(x=>({x:x.period_end,y:x.value}));box.appendChild(drawLineChart(points));paragraph(box,"User-provided CSV; price adjustment and provenance not verified.");parent.appendChild(box);const notes=section("Technical observations"),list=el("ul");(a.claims||[]).forEach(x=>list.appendChild(el("li","",x)));notes.appendChild(list);(a.limitations||[]).forEach(x=>paragraph(notes,x));parent.appendChild(notes)}
function renderSources(parent){const entries=sources(),box=section(entries.length+" source record(s)"),wrap=el("div","table-wrap"),t=el("table"),head=el("thead"),h=el("tr");["Agent","Source","Reference","Published","Observed","Type"].forEach(s=>h.appendChild(el("th","",s)));head.appendChild(h);t.appendChild(head);const tbody=el("tbody");entries.forEach(s=>{const r=el("tr");r.appendChild(el("td","",s.agent));r.appendChild(el("td","",s.source_name));const cell=el("td"),link=el("a","source-link",s.text_excerpt||s.source_id);link.href=s.source_url;link.target="_blank";link.rel="noopener noreferrer";cell.appendChild(link);r.appendChild(cell);r.appendChild(el("td","",s.published_at?.slice(0,10)||"—"));r.appendChild(el("td","",s.observed_at?.slice(0,10)||"—"));r.appendChild(el("td","",s.is_synthetic?"SYNTHETIC":"Original / unverified"));tbody.appendChild(r)});t.appendChild(tbody);wrap.appendChild(t);box.appendChild(wrap);parent.appendChild(box);paragraph(parent,"Source links may represent metadata only. Filings and full news articles have not necessarily been read.")}
function renderAgents(parent){agents().forEach(a=>{const details=el("details","agent-details"),summary=el("summary","",a.agent_id.replaceAll("_"," "));summary.appendChild(badge(a.status));details.appendChild(summary);const content=el("div","agent-body");paragraph(content,a.summary||"No summary.");if(a.claims?.length){content.appendChild(el("h4","","Findings"));const ul=el("ul");a.claims.forEach(x=>ul.appendChild(el("li","",x)));content.appendChild(ul)}if(Object.keys(a.metrics||{}).length){content.appendChild(el("h4","","Metrics"));content.appendChild(table(["Metric","Value"],Object.entries(a.metrics)))}if(a.limitations?.length){content.appendChild(el("h4","","Limitations"));const ul=el("ul");a.limitations.forEach(x=>ul.appendChild(el("li","",x)));content.appendChild(ul)}details.appendChild(content);parent.appendChild(details)})}
function renderJSON(parent){const box=section("Structured report");box.appendChild(el("pre","json-block",JSON.stringify(state.report,null,2)));parent.appendChild(box)}
$("downloadReport").onclick=()=>{if(!state.report)return;const blob=new Blob([JSON.stringify(state.report,null,2)],{type:"application/json"}),url=URL.createObjectURL(blob),a=el("a");a.href=url;a.download="fa_"+state.report.request.symbol+"_"+Date.now()+".json";document.body.appendChild(a);a.click();a.remove();URL.revokeObjectURL(url)};
restoreHistory();loadCapabilities();


function renderQuote(parent){
  const result=state.report?.market_quote;
  if(!result)return;
  const quote=result.selected;
  if(!quote){paragraph(parent,"No confirmed quote was returned by the selected market providers.");}
  else{
    const card=el("section","report-lead");
    card.appendChild(el("h3","",quote.instrument+" · "+quote.symbol));
    card.appendChild(el("h1","",fmt(quote.price)+" "+quote.currency));
    paragraph(card,quote.venue+" · "+quote.provider.toUpperCase()+" · "+
      new Date(quote.at).toLocaleString("en-GB",{timeZone:"UTC"})+" UTC");
    paragraph(card,quote.caveat);
    parent.appendChild(card);
    if(quote.history?.length||quote.bars?.length){
      const chart=section("Interactive market chart · "+(quote.bar_interval||"price observations"));
      if(window.FAInteractiveChart){
        chart.appendChild(window.FAInteractiveChart.createInteractiveChart({
          bars:quote.bars||[],history:quote.history||[],currency:quote.currency
        }));
      }else{
        chart.appendChild(drawLineChart((quote.history||[]).map(p=>({x:p.at.slice(0,16),y:p.price}))));
      }
      paragraph(chart,"Hover to inspect values; mouse wheel zooms, drag pans. Candles require original OHLC data. Price may be delayed.");
      parent.appendChild(chart);
    }
  }
  title(parent,"Market data specialists");
  parent.appendChild(table(["Provider","Instrument","Venue","Last price","Currency","Timestamp UTC","Result"],
    (result.attempts||[]).map(a=>[
      a.provider.toUpperCase(),a.symbol,a.quote?.venue||"—",
      a.quote?.price??"—",a.quote?.currency||"—",
      a.quote?.at?.replace("T"," ").slice(0,19)||"—",
      a.status==="ok"?"Retrieved":a.error||a.status
    ])));
  paragraph(parent,
    "Yahoo Finance uses an unofficial endpoint; Binance Spot uses public REST market data. "+
    "TradingView requires a separately configured authorized adapter. "+
    "Prices from USD and USDT pairs are shown separately and are never averaged.");
}


function renderSpecialistTopic(parent,selected){
  for(const id of selected){
    const r=agent(id);
    if(!r)continue;
    title(parent,id.replaceAll("_"," "));
    const card=section(r.summary||"Specialist findings");
    const grid=document.createElement("div");grid.className="kpi-grid";
    for(const [key,val] of Object.entries(r.metrics||{})){
      if(val!==null&&val!==undefined)grid.appendChild(valueRow(key,val));
    }
    if(grid.childElementCount)card.appendChild(grid);
    if(r.claims?.length){
      const heading=document.createElement("h4");heading.textContent="Source-backed observations";
      card.appendChild(heading);
      const ul=document.createElement("ul");
      r.claims.forEach(c=>{const li=document.createElement("li");li.textContent=c;ul.appendChild(li)});
      card.appendChild(ul);
    }
    const sources=(r.evidence||[]);
    if(sources.length){
      const h=document.createElement("h4");h.textContent="Primary references";card.appendChild(h);
      const list=document.createElement("ul");
      sources.slice(0,15).forEach(s=>{
        const li=document.createElement("li"),a=document.createElement("a");
        a.className="source-link";a.href=s.source_url;a.target="_blank";
        a.rel="noopener noreferrer";a.textContent=s.text_excerpt||s.source_id;
        li.appendChild(a);list.appendChild(li);
      });
      card.appendChild(list);
    }
    if(r.limitations?.length){
      const h=document.createElement("h4");h.textContent="Coverage and limitations";card.appendChild(h);
      const list=document.createElement("ul");
      r.limitations.forEach(c=>{const li=document.createElement("li");li.textContent=c;list.appendChild(li)});
      card.appendChild(list);
    }
    parent.appendChild(card);
  }
}


function renderCot(parent){
  const result=agent("cot");if(!result)return;
  const cot=result.cot;
  if(!cot){
    const card=section("COT · Contract not identified");
    paragraph(card,result.summary||"No COT records available.");
    (result.limitations||[]).forEach(line=>paragraph(card,line));
    parent.appendChild(card);return;
  }
  if(cot.markets?.length){
    const panel=section("Select a CFTC futures contract");
    paragraph(panel,"Several market contracts match this question. Choose the exact futures contract; COT is not published for individual company shares.");
    const controls=el("div","cot-controls"),picker=el("select");
    cot.markets.forEach(m=>{
      const opt=el("option","",m.market+" · "+m.name+" ["+m.code+"]");
      opt.value=m.code;picker.appendChild(opt);
    });
    const button=el("button","primary","Load selected contract");
    button.type="button";button.onclick=()=>{
      if(state.running)return;
      const selected=cot.markets.find(m=>m.code===picker.value);
      if(!selected)return;
      $("mode").value="live";$("mode").dispatchEvent(new Event("change"));
      state.cotMarketCode=selected.code;state.cotReportType=cot.report_type;
      state.cotForceAgents=true;
      $("question").value="COT do contrato "+selected.market+" ("+selected.code+")";
      $("chatForm").requestSubmit();
    };
    controls.append(picker,button);panel.appendChild(controls);
    parent.appendChild(panel);return;
  }
  if(!cot.latest){paragraph(parent,"No usable weekly reports were returned.");return;}
  const latest=cot.latest,card=el("section","report-lead");
  card.appendChild(el("h3","",(cot.market_name||"Contract")+" · "+cot.market_code));
  paragraph(card,"CFTC "+cot.report_type.toUpperCase()+" · Futures only · Position report "+latest.report_date+" · "+cot.source);
  const stats=el("div","kpi-grid");
  append(stats,valueRow("Open interest (contracts)",latest.open_interest),valueRow("Report date",latest.report_date),valueRow("History (weeks)",(cot.weeks||[]).length));
  card.appendChild(stats);parent.appendChild(card);
  title(parent,"Traders' latest positions");
  parent.appendChild(table(["Category","Long","Short","Net","Net / OI %","Δ weekly net"],
    latest.groups.map(g=>[g.group,g.long,g.short,g.net,g.net_pct_oi,g.net_wow??"—"])));
  const weeks=cot.weeks||[];
  if(weeks.length){
    const chart=section("Weekly net positions by trader category");
    const controls=el("div","cot-controls"),label=el("span","muted-note","Trader category"),picker=el("select");
    latest.groups.forEach(g=>{const option=el("option","",g.group);option.value=g.group;picker.appendChild(option)});
    controls.append(label,picker);chart.appendChild(controls);
    const graphic=el("div","cot-plot");chart.appendChild(graphic);
    const redraw=()=>{
      clear(graphic);
      const series=weeks.map(w=>{
        const r=(w.groups||[]).find(p=>p.group===picker.value);
        return r?{at:w.report_date+"T00:00:00Z",price:r.net}:null;
      }).filter(Boolean);
      if(window.FAInteractiveChart){
        graphic.appendChild(window.FAInteractiveChart.createInteractiveChart({
          history:series,currency:"contracts",seriesLabel:"Net positioning"
        }));
      }else{
        graphic.appendChild(drawLineChart(series.map(p=>({x:p.at,y:p.price}))));
      }
    };
    picker.onchange=redraw;redraw();
    paragraph(chart,"COT report dates are Tuesday snapshots, not release timestamps. Zoom and pan the historical chart.");
    parent.appendChild(chart);
    title(parent,"Historical COT data");
    parent.appendChild(table(["Report date","Open interest",...latest.groups.map(g=>g.group+" net")],
      [...weeks].reverse().map(w=>[w.report_date,w.open_interest,
        ...latest.groups.map(g=>(w.groups||[]).find(x=>x.group===g.group)?.net??"—")])));
  }
  const limitations=section("Interpretation and limitations");
  (result.limitations||[]).forEach(line=>paragraph(limitations,line));
  parent.appendChild(limitations);
}


function renderCryptoDerivatives(parent){
  const result=agent("crypto_derivatives");
  if(!result)return;
  const data=result.crypto_derivatives;
  if(!data){
    const card=section("Crypto derivatives · Data unavailable");
    paragraph(card,result.summary);
    (result.limitations||[]).forEach(x=>paragraph(card,x));
    parent.appendChild(card);
    return;
  }
  const panel=el("section","report-lead");
  panel.appendChild(el("h3","",data.instrument+" · "+data.provider));
  paragraph(panel,"Market "+data.market_type+" · Retrieved "+data.retrieved_at.slice(0,19)+" UTC");
  const stats=el("div","kpi-grid");
  for(const [metric,label] of [
    ["funding_rate_pct","Last settled funding (%)"],
    ["open_interest","Open interest (base asset)"],
    ["global_long_short_account_ratio","Long / short accounts ratio"]
  ]){
    if(result.metrics?.[metric]!==undefined){
      stats.appendChild(valueRow(label,result.metrics[metric]));
    }
  }
  if(stats.childElementCount)panel.appendChild(stats);
  parent.appendChild(panel);
  const series=data.series||[];
  const keys=[...new Set(series.map(x=>x.metric))];
  if(keys.length){
    const chart=section("Historical Binance Futures observations");
    const toolbar=el("div","cot-controls"),picker=el("select");
    keys.forEach(key=>{const option=el("option","",key.replaceAll("_"," "));option.value=key;picker.appendChild(option)});
    toolbar.appendChild(picker);chart.appendChild(toolbar);
    const plot=el("div","cot-plot");chart.appendChild(plot);
    const redraw=()=>{
      clear(plot);
      const selected=series.filter(x=>x.metric===picker.value);
      if(selected.length>1){
        const points=selected.map(x=>({at:x.at,price:x.value}));
        if(window.FAInteractiveChart){
          plot.appendChild(window.FAInteractiveChart.createInteractiveChart({
            history:points,currency:selected[0]?.unit||"",
            seriesLabel:picker.value.replaceAll("_"," ")
          }));
        }else plot.appendChild(drawLineChart(points.map(x=>({x:x.at,y:x.price}))));
      }else{
        plot.appendChild(el("p","muted-note","Only one snapshot is available. A historical chart requires at least two observations."));
      }
    };
    picker.onchange=redraw;redraw();
    paragraph(chart,"Funding rates are settlement observations per funding interval. Long/short ratios count accounts, not contracts. Open interest is a timestamped snapshot.");
    parent.appendChild(chart);
    title(parent,"All source observations");
    parent.appendChild(table(["Metric","Time (UTC)","Value","Unit"],
      [...series].sort((a,b)=>b.at.localeCompare(a.at)).map(x=>[
        x.metric.replaceAll("_"," "),x.at.slice(0,19).replace("T"," "),x.value,x.unit
      ])));
  }
  const info=section("Provider and scope");
  (result.limitations||[]).forEach(x=>paragraph(info,x));
  parent.appendChild(info);
}
