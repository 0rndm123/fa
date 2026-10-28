"use strict";
// Settings are persisted by the local FA_Agent server; no API key is exposed here.
(() => {
  const $ = id => document.getElementById(id);
  const body = $("modelSettingsBody");
  const status = $("modelSettingsStatus");
  let config = null;
  let catalog = null;
  let initialized = false;

  function element(tag, text, className) {
    const x = document.createElement(tag);
    if (text !== undefined) x.textContent = text;
    if (className) x.className = className;
    return x;
  }
  function modelField(label, id, value, choices, description) {
    const item = element("div", undefined, "model-field");
    item.appendChild(element("label", label));
    const input = element("input");
    input.type = "text";
    input.id = id;
    input.value = value;
    input.maxLength = 96;
    input.setAttribute("list", id+"-choices");
    input.setAttribute("aria-label", label);
    const list = element("datalist");list.id = id+"-choices";
    for (const model of choices) {
      const option = element("option");
      option.value = model;
      list.appendChild(option);
    }
    item.appendChild(input);
    item.appendChild(list);
    if (description) item.appendChild(element("small", description, "muted-note"));
    return item;
  }
  function selectField(label, id, value, choices) {
    const item = element("div", undefined, "model-field");
    const name = element("label", label);name.htmlFor=id;item.appendChild(name);
    const select=element("select");select.id=id;
    for(const [v,t] of choices){const option=element("option",t);option.value=v;option.selected=v===value;select.appendChild(option)}
    item.appendChild(select);return item;
  }
  function openSettings(open) {
    $("resultsPane").classList.toggle("settings-open", open);
    $("modelSettingsPane").classList.toggle("hidden", !open);
    $("modelsViewTab").setAttribute("aria-selected", String(open));
    $("researchViewTab").setAttribute("aria-selected", String(!open));
    if(open&&!initialized) void refresh();
  }
  $("modelsViewTab").onclick=()=>openSettings(true);
  $("researchViewTab").onclick=()=>openSettings(false);
  function render() {
    initialized=true;
    body.replaceChildren();
    const functions=element("section",undefined,"data-box");
    functions.appendChild(element("h2","Modelos por funcionalidade","section-title"));
    const desc=element("p","A lista é indicativa. O acesso depende dos modelos disponíveis na tua conta OpenAI; podes introduzir outro ID. Cada configuração é aplicada à próxima chamada.", "muted-note");
    functions.appendChild(desc);
    const grid=element("div",undefined,"models-grid");
    grid.appendChild(modelField("Síntese geral e resposta escrita","settings-synthesis",
      config.synthesis,catalog.text_models,"Usado quando a opção AI commentary está ativa."));
    grid.appendChild(modelField("Transcrição de voz","settings-transcription",
      config.transcription,catalog.transcription_models,"Reconhecimento de fala, não gera análises."));
    grid.appendChild(modelField("Resposta falada (TTS)","settings-speech",
      config.speech,catalog.speech_models,"Geração de áudio a partir da resposta textual."));
    grid.appendChild(selectField("Voz","settings-voice",config.voice,catalog.voices.map(v=>[v,v])));
    grid.appendChild(selectField("Idioma da transcrição","settings-language",config.language,
      [["auto","Automático"],["pt","Português"],["en","Inglês"],["es","Espanhol"],["fr","Francês"],["de","Alemão"]]));
    functions.appendChild(grid);body.appendChild(functions);

    const agents=element("section",undefined,"data-box");
    agents.appendChild(element("h2","Modelos por agente","section-title"));
    agents.appendChild(element("p","Os agentes consultam fontes e calculam indicadores sem LLM. Ativa comentários de IA apenas nos especialistas em que pretendes uma interpretação adicional. São executados no máximo quatro por pergunta e requerem AI commentary ativo.", "muted-note"));
    const table=element("div",undefined,"model-agent-grid");
    for(const entry of catalog.agents){
      const row=element("div",undefined,"agent-model-row");
      const label=element("div");label.appendChild(element("strong",entry.id.replaceAll("_"," ")));
      label.appendChild(element("small",entry.description,"muted-note"));row.appendChild(label);
      const model=modelField("Modelo para "+entry.id,"agent-model-"+entry.id,
        config.agent_models[entry.id]||"",catalog.text_models,
        "Em branco herda o modelo de síntese geral.");
      model.querySelector("input").placeholder="Herdar modelo geral";
      row.appendChild(model);
      const enable=element("label",undefined,"checkline");
      const checkbox=element("input");checkbox.type="checkbox";checkbox.id="agent-enabled-"+entry.id;
      checkbox.checked=config.agent_ai_enabled.includes(entry.id);
      enable.appendChild(checkbox);enable.appendChild(element("span","Comentário IA"));
      row.appendChild(enable);table.appendChild(row);
    }
    agents.appendChild(table);body.appendChild(agents);
    const limits=element("p",catalog.notes.join(" "),"muted-note");body.appendChild(limits);
  }
  async function refresh(){
    status.textContent="A carregar…";
    try{
      const response=await fetch("/api/model-settings",{cache:"no-store"});
      const result=await response.json();
      if(!response.ok)throw Error(result.detail||"Não foi possível ler configurações.");
      config=result.settings;catalog=result.catalog;render();status.textContent="Configurações atuais.";
    }catch(error){status.textContent=String(error.message||error)}
  }
  function collect(){
    if(!catalog)throw Error("Configuração ainda não carregada.");
    const data={
      synthesis:$("settings-synthesis").value.trim(),
      transcription:$("settings-transcription").value.trim(),
      speech:$("settings-speech").value.trim(),
      voice:$("settings-voice").value,
      language:$("settings-language").value,
      agent_models:{},agent_ai_enabled:[]
    };
    for(const entry of catalog.agents){
      const id=entry.id;
      const value=$("agent-model-"+id).value.trim();
      if(value)data.agent_models[id]=value;
      if($("agent-enabled-"+id).checked)data.agent_ai_enabled.push(id);
    }
    return data;
  }
  $("modelSettingsSave").onclick=async()=>{
    status.textContent="A guardar…";
    try{
      const response=await fetch("/api/model-settings",{
        method:"PUT",headers:{"Content-Type":"application/json"},body:JSON.stringify(collect())
      });
      const result=await response.json();
      if(!response.ok)throw Error(result.detail||"Não foi possível guardar.");
      config=result.settings;catalog=result.catalog;render();
      status.textContent="Configuração guardada. Será utilizada nas próximas chamadas.";
    }catch(error){status.textContent="Erro: "+String(error.message||error)}
  };
  $("modelSettingsReset").onclick=()=>{
    if(!catalog)return;
    config={
      synthesis:"gpt-4.1-mini",transcription:"gpt-4o-mini-transcribe",
      speech:"gpt-4o-mini-tts",voice:"alloy",language:"auto",
      agent_models:{},agent_ai_enabled:[]
    };
    render();
    status.textContent="Valores repostos no formulário. Carrega em Guardar para aplicar.";
  };
  void refresh();
})();
