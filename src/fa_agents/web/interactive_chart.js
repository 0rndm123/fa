"use strict";
/* Small dependency-free OHLC chart for the FA local workbench.
   Real OHLC data only. Never infer or fabricate candles from closing prices. */
(function(){
const NS="http://www.w3.org/2000/svg";
function node(tag,attrs={},value=null){
  const n=document.createElementNS(NS,tag);
  for(const [k,v] of Object.entries(attrs))n.setAttribute(k,String(v));
  if(value!==null)n.textContent=String(value);
  return n;
}
function html(tag,cls="",text=null){
  const n=document.createElement(tag);n.className=cls;
  if(text!==null)n.textContent=text;
  return n;
}
function compact(v){
  if(Math.abs(v)>=10000)return v.toLocaleString("en-US",{maximumFractionDigits:1});
  return v.toFixed(Math.abs(v)<2?4:2);
}
function createInteractiveChart({bars=[],history=[],currency=""}={}){
  const cleanBar=bars.filter(x=>
    x && Number.isFinite(+x.open)&&Number.isFinite(+x.high)&&
    Number.isFinite(+x.low)&&Number.isFinite(+x.close)&&
    +x.low<=Math.min(+x.open,+x.close)&&Math.max(+x.open,+x.close)<=+x.high
  ).sort((a,b)=>a.at.localeCompare(b.at));
  const cleanLine=history.filter(x=>x && Number.isFinite(+x.price)).sort((a,b)=>a.at.localeCompare(b.at));
  const points=(cleanLine.length?cleanLine:cleanBar.map(x=>({at:x.at,price:x.close}))).slice(-500);
  const candles=cleanBar.slice(-500);
  const root=html("div","market-chart-widget"),toolbar=html("div","market-chart-toolbar");
  const title=html("span","market-chart-help","Scroll to zoom · Drag to pan · Hover for values");
  let kind=candles.length?"candles":"line";
  const btnLine=html("button","chart-mode","Line");
  const btnCandle=html("button","chart-mode","Candles");
  btnLine.type="button";btnCandle.type="button";
  btnCandle.disabled=!candles.length;
  btnCandle.title=candles.length?"Show true OHLC bars":"OHLC not supplied by provider";
  const reset=html("button","chart-reset","Reset");reset.type="button";
  const modes=html("div","market-chart-modes");
  modes.append(btnLine,btnCandle,reset);
  toolbar.append(title,modes);root.appendChild(toolbar);
  const wrap=html("div","market-chart-canvas"),svg=node("svg",{viewBox:"0 0 900 350",role:"img","aria-label":"Interactive financial price chart"}),
    tip=html("div","market-chart-tooltip");
  wrap.append(svg,tip);root.appendChild(wrap);
  let total=(kind==="candles"?candles:points).length;
  let viewCount=Math.min(70,total),end=total,hover=-1,drag=null;
  const W=900,H=350,L=75,R=20,T=24,B=38,drawW=W-L-R,drawH=H-T-B;
  function dataset(){return kind==="candles"?candles:points}
  function resetView(){
    total=dataset().length;viewCount=Math.min(70,total);end=total;hover=-1;draw();
  }
  function switchMode(next){
    if(next==="candles"&&!candles.length)return;
    kind=next;resetView();
  }
  btnLine.onclick=()=>switchMode("line");
  btnCandle.onclick=()=>switchMode("candles");
  reset.onclick=resetView;
  function renderTip(item){
    if(!item){tip.style.display="none";return}
    const stamp=item.at.replace("T"," ").slice(0,19)+" UTC";
    if(kind==="candles"){
      tip.textContent=stamp+" | O "+compact(+item.open)+"  H "+compact(+item.high)+
        "  L "+compact(+item.low)+"  C "+compact(+item.close)+" "+currency;
    }else{
      tip.textContent=stamp+" | Close "+compact(+item.price)+" "+currency;
    }
    tip.style.display="block";
  }
  function draw(){
    svg.replaceChildren();
    const data=dataset();
    btnLine.classList.toggle("active",kind==="line");
    btnCandle.classList.toggle("active",kind==="candles");
    total=data.length;
    if(!total){svg.appendChild(node("text",{x:W/2,y:H/2,"text-anchor":"middle",fill:"#95aabd"},"No timestamped prices available"));return}
    viewCount=Math.min(Math.max(1,viewCount),total);
    end=Math.min(Math.max(end,viewCount),total);
    const start=end-viewCount,visible=data.slice(start,end);
    const vals=kind==="candles"?visible.flatMap(b=>[+b.high,+b.low]):visible.map(b=>+b.price);
    let min=Math.min(...vals),max=Math.max(...vals);
    if(max===min){const d=Math.max(1,Math.abs(max)*.005);max+=d;min-=d}
    const pad=(max-min)*0.06;max+=pad;min-=pad;
    const Y=v=>T+((max-v)/(max-min))*drawH;
    const X=i=>L+(i+0.5)/visible.length*drawW;
    for(let i=0;i<=5;i++){
      const value=max-(max-min)*i/5,y=Y(value);
      svg.appendChild(node("line",{x1:L,x2:W-R,y1:y,y2:y,stroke:"#374658","stroke-width":1}));
      svg.appendChild(node("text",{x:L-10,y:y+4,fill:"#97acc1","text-anchor":"end","font-size":11},compact(value)));
    }
    const tickCount=Math.min(5,visible.length);
    for(let i=0;i<tickCount;i++){
      const idx=tickCount===1?0:Math.round(i*(visible.length-1)/(tickCount-1));
      svg.appendChild(node("text",{x:X(idx),y:H-12,fill:"#8da4bb","text-anchor":"middle","font-size":11},
        visible[idx].at.slice(5,16).replace("T"," ")));
    }
    if(kind==="candles"){
      const width=Math.max(1.6,Math.min(13,drawW/visible.length*.64));
      visible.forEach((b,i)=>{
        const up=+b.close>=+b.open,color=up?"#36c6a5":"#eb7187",cx=X(i);
        svg.appendChild(node("line",{x1:cx,x2:cx,y1:Y(+b.high),y2:Y(+b.low),stroke:color,"stroke-width":1.4}));
        const y=Math.min(Y(+b.open),Y(+b.close)),height=Math.max(1.5,Math.abs(Y(+b.open)-Y(+b.close)));
        svg.appendChild(node("rect",{x:cx-width/2,y,width,height,fill:color,rx:.4}));
      });
    }else{
      const poly=node("polyline",{points:visible.map((p,i)=>X(i).toFixed(2)+","+Y(+p.price).toFixed(2)).join(" "),
        stroke:"#73baff","stroke-width":2.3,fill:"none","stroke-linejoin":"round"});
      svg.appendChild(poly);
    }
    if(hover>=0&&hover<visible.length){
      const item=visible[hover],cx=X(hover),v=kind==="candles"?+item.close:+item.price;
      svg.appendChild(node("line",{x1:cx,x2:cx,y1:T,y2:T+drawH,stroke:"#aac9e7","stroke-dasharray":"3 4",opacity:.8}));
      svg.appendChild(node("circle",{cx,cy:Y(v),r:4,stroke:"#f2f7ff","stroke-width":1.5,fill:"#1c425f"}));
      renderTip(item);
    }else renderTip(null);
  }
  function localX(event){
    const r=svg.getBoundingClientRect();
    return ((event.clientX-r.left)/r.width)*W;
  }
  svg.addEventListener("pointermove",event=>{
    if(drag){
      const dx=localX(event)-drag.x;
      const barsToMove=Math.round(dx/(drawW/Math.max(1,viewCount)));
      end=Math.min(total,Math.max(viewCount,drag.end-barsToMove));hover=-1;draw();return;
    }
    const x=localX(event);
    hover=(x<L||x>W-R)?-1:Math.min(viewCount-1,Math.max(0,Math.floor((x-L)/drawW*viewCount)));
    draw();
  });
  svg.addEventListener("pointerleave",()=>{if(!drag){hover=-1;draw()}});
  svg.addEventListener("pointerdown",event=>{
    if(event.button!==0)return;
    drag={x:localX(event),end};svg.setPointerCapture(event.pointerId);
    svg.style.cursor="grabbing";
  });
  function stopDrag(){drag=null;svg.style.cursor="crosshair"}
  svg.addEventListener("pointerup",stopDrag);
  svg.addEventListener("pointercancel",stopDrag);
  svg.addEventListener("wheel",event=>{
    event.preventDefault();
    const direction=event.deltaY>0?1.25:0.8;
    const newCount=Math.min(total,Math.max(Math.min(8,total),Math.round(viewCount*direction)));
    if(newCount===viewCount)return;
    const oldStart=end-viewCount;
    const fraction=Math.max(0,Math.min(1,(localX(event)-L)/drawW));
    const anchor=oldStart+fraction*viewCount;
    viewCount=newCount;
    const newStart=Math.round(anchor-fraction*newCount);
    end=Math.min(total,Math.max(viewCount,newStart+viewCount));
    hover=-1;draw();
  },{passive:false});
  draw();
  return root;
}
window.FAInteractiveChart={createInteractiveChart};
})();
