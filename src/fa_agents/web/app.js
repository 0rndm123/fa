"use strict";
const $=id=>document.getElementById(id);
const state={report:null,activeTab:"overview",selectedAgents:null,uploadId:null,capabilities:null,running:false,metric:"revenue",messages:[]};
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
function drawMessage(role,content,save=true){const n=el("div","message "+role);n.appendChild(el("span","message-role",role==="user"?"YOU":"FA AGENT"));n.appendChild(el("p","",content));$("messages").appendChild(n);$("messages").scrollTop=$("messages").scrollHeight;if(save){state.messages.push({role,content});saveChat()}}
function restoreHistory(){try{const x=JSON.parse(sessionStorage.getItem("fa-chat-session-v1")||"[]");if(Array.isArray(x))state.messages=x.slice(-40).filter(v=>v&&["user","assistant"].includes(v.role)&&typeof v.content==="string")}catch{}if(state.messages.length){clear($("messages"));state.messages.forEach(x=>drawMessage(x.role,x.content,false))}}
function toggleChat(mode){const mini=workspace.classList.contains("chat-minimized"),maxi=workspace.classList.contains("chat-maximized");workspace.classList.remove("chat-minimized","chat-maximized");if(mode==="min"&&!mini)workspace.classList.add("chat-minimized");if(mode==="max"&&!maxi)workspace.classList.add("chat-maximized");$("chatMaximize").textContent=workspace.classList.contains("chat-maximized")?"⇲":"⛶";$("chatMaximize").title=workspace.classList.contains("chat-maximized")?"Restore split view":"Maximize chat"}
$("chatMinimize").onclick=()=>toggleChat("min");$("chatMaximize").onclick=()=>toggleChat("max");$("chatExpandRail").onclick=()=>toggleChat("min");
(function(){const handle=$("resizeHandle");handle.addEventListener("pointerdown",event=>{if(window.innerWidth<800||workspace.classList.contains("chat-minimized")||workspace.classList.contains("chat-maximized"))return;event.preventDefault();handle.setPointerCapture(event.pointerId);const move=e=>{const bound=workspace.getBoundingClientRect();workspace.style.setProperty("--chat-size",Math.max(270,Math.min(bound.width*.65,e.clientX-bound.left))+"px")};const stop=()=>{handle.removeEventListener("pointermove",move);handle.removeEventListener("pointerup",stop);handle.removeEventListener("pointercancel",stop)};handle.addEventListener("pointermove",move);handle.addEventListener("pointerup",stop);handle.addEventListener("pointercancel",stop)})})();
function agentCount(){$("agentCount").textContent=state.selectedAgents===null?"Auto":state.selectedAgents.length+" selected"}
async function loadCapabilities(){try{const r=await fetch("/api/capabilities",{cache:"no-store"});if(!r.ok)throw Error("Server unavailable");state.capabilities=await r.json();const list=clear($("agentChoices"));state.capabilities.agents.forEach(a=>{const l=el("label"),input=el("input");input.type="checkbox";input.value=a.id;input.onchange=()=>{state.selectedAgents=[...list.querySelectorAll("input:checked")].map(x=>x.value);agentCount()};const text=el("span","",a.id.replaceAll("_"," "));text.title=a.description+" ("+a.implementation+")";if(a.implementation==="planned")text.style.color="#72879c";append(l,input,text);list.appendChild(l)});$("useLLM").disabled=!state.capabilities.llm_configured||$("mode").value==="demo";$("useLLM").title=state.capabilities.llm_configured?"Optional AI commentary":"Set OPENAI_API_KEY_Demo or OPENAI_API_KEY";$("connectionStatus").textContent=(state.capabilities.llm_configured?"AI ready":"AI key unavailable")+" · "+(state.capabilities.sec_configured?"SEC ready":"SEC identity not configured")}catch(err){$("connectionStatus").textContent="Server error";showError(String(err.message))}}
$("agentToggle").onclick=()=>$("agentPanel").classList.toggle("hidden");
$("allAgents").onclick=()=>{const nodes=[...$("agentChoices").querySelectorAll("input")];nodes.forEach(x=>x.checked=true);state.selectedAgents=nodes.map(x=>x.value);agentCount()};
$("clearAgents").onclick=()=>{$("agentChoices").querySelectorAll("input").forEach(x=>x.checked=false);state.selectedAgents=[];agentCount()};
$("defaultAgents").onclick=()=>{$("agentChoices").querySelectorAll("input").forEach(x=>x.checked=false);state.selectedAgents=null;agentCount()};
$("mode").onchange=()=>{const demo=$("mode").value==="demo";$("symbol").disabled=demo;if(demo){$("symbol").value="DEMO";$("useLLM").checked=false}else if($("symbol").value==="DEMO")$("symbol").value="NVDA";$("useLLM").disabled=demo||!(state.capabilities&&state.capabilities.llm_configured);if(demo)showError("DEMO MODE: company figures and news are synthetic.");else hideError()};
$("mode").dispatchEvent(new Event("change"));
$("priceUpload").onchange=async event=>{const file=event.target.files[0];if(!file)return;$("uploadLabel").textContent="Uploading "+file.name+"…";try{const form=new FormData();form.append("file",file);const r=await fetch("/api/upload-prices",{method:"POST",body:form});const data=await r.json();if(!r.ok)throw Error(data.detail||"CSV rejected");state.uploadId=data.upload_id;$("uploadLabel").textContent=file.name+" ("+data.observations+" rows)";hideError()}catch(err){state.uploadId=null;$("uploadLabel").textContent="Upload failed";showError(String(err.message))}};
$("clearChat").onclick=()=>{state.messages=[];saveChat();clear($("messages"));drawMessage("assistant","Conversation cleared. Start a new research question.")};
async function submitQuery(event){event.preventDefault();if(state.running)return;const q=$("question").value.trim();if(!q)return;const history=state.messages.slice(-8).map(x=>({role:x.role,content:x.content.slice(0,2000)}));drawMessage("user",q);$("question").value="";$("emptyState").classList.add("hidden");$("busy").classList.remove("hidden");$("submit").disabled=true;state.running=true;hideError();$("reportBadge").textContent="RUNNING";const payload={symbol:$("symbol").value.trim().toUpperCase(),asset_class:$("assetClass").value,mode:$("mode").value,question:q,horizon:$("horizon").value,agents:state.cotForceAgents?["cot"]:state.selectedAgents,llm:$("useLLM").checked,price_upload_id:state.uploadId,history};try{const response=await fetch("/api/analyze",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(payload)});const data=await response.json();if(!response.ok)throw Error(typeof data.detail==="string"?data.detail:JSON.stringify(data.detail));state.report=data.report;drawMessage("assistant",data.answer);renderReport();if(workspace.classList.contains("chat-maximized"))toggleChat("max")}catch(err){const msg="Research failed: "+String(err.message||err);drawMessage("assistant",msg);showError(msg);$("reportBadge").textContent="ERROR"}finally{$("busy").classList.add("hidden");$("submit").disabled=false;state.running=false}}
$("chatForm").onsubmit=submitQuery;
$("question").onkeydown=event=>{if(event.key==="Enter"&&!event.shiftKey){event.preventDefault();$("chatForm").requestSubmit()}};
function agents(){return state.report?.results||[]}
function agent(id){return agents().find(x=>x.agent_id===id)||null}
function sources(){const seen=new Set(),items=[];agents().forEach(a=>(a.evidence||[]).forEach(e=>{const key=e.source_id+"|"+e.source_url;if(seen.has(key))return;seen.add(key);items.push({...e,agent:a.agent_id})}));return items}
function renderReport(){const r=state.report;if(!r)return;$("downloadReport").disabled=false;$("resultTitle").textContent=r.request.symbol+" · Research analysis";$("resultSubtitle").textContent=(r.data_mode==="demo"?"SYNTHETIC DEMO":"Live research")+" · "+r.generated_at.slice(0,19).replace("T"," ")+" UTC · "+agents().length+" specialists";$("reportBadge").textContent=r.status.toUpperCase().replaceAll("_"," ");$("reportBadge").className="status-pill "+(r.status==="completed"?"good":r.status==="partial"?"warn":"");if(r.warnings?.length)showError(r.warnings.join("\n"));else hideError();$("emptyState").classList.add("hidden");$("reportArea").classList.remove("hidden");const tabs=[...(r.market_quote?[["quote","Quote"]]:[]),["overview","Overview"],...(agent("financial_data")?.observations?.length||agent("fundamental")?.metrics?[["financial","Financials"]]:[]),...(agent("technical")?[["technical","Technical"]]:[]),
    ...(agent("debt_liquidity")?[["debt","Debt & Liquidity"]]:[]),
    ...(agent("governance")?[["governance","Governance"]]:[]),
    ...(agent("competition")||agent("industry_context")?[["sector","Sector & Peers"]]:[]),...(sources().length?[["sources","Sources"]]:[]),["agents","Specialists"],["json","JSON"]];state.tabs=tabs;if(r.market_quote)state.activeTab="quote";else if(!tabs.some(x=>x[0]===state.activeTab))state.activeTab="overview";const nav=clear($("tabs"));tabs.forEach(([id,text])=>{const n=el("button","tab",text);n.type="button";n.setAttribute("role","tab");n.dataset.id=id;n.onclick=()=>{state.activeTab=id;renderTab()};nav.appendChild(n)});renderTab()}
function renderTab(){for(const node of $("tabs").children)node.setAttribute("aria-selected",node.dataset.id===state.activeTab?"true":"false");const parent=clear($("tabContent"));switch(state.activeTab){case"quote":renderQuote(parent);break;case"overview":renderOverview(parent);break;case"financial":renderFinancial(parent);break;case"technical":renderTechnical(parent);break;case"debt":renderSpecialistTopic(parent,["debt_liquidity"]);break;case"governance":renderSpecialistTopic(parent,["governance"]);break;case"sector":renderSpecialistTopic(parent,["industry_context","competition"]);break;case"sources":renderSources(parent);break;case"agents":renderAgents(parent);break;case"json":renderJSON(parent);break}}
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
