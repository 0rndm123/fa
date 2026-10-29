"use strict";
// Opt-in turn-based audio research. Microphone is OFF unless activated by a user.
// Recording ends on button press or (in automatic mode) a bounded silence pause.
(() => {
  const mic = document.getElementById("voiceMic");
  const stop = document.getElementById("voiceStop");
  const auto = document.getElementById("voiceAuto");
  const status = document.getElementById("voiceConversationStatus");
  let phase = "idle";
  let recorder = null;
  let stream = null;
  let chunks = [];
  let timer = null;
  let vadTimer = null;
  let audioContext = null;
  let player = null;
  let audioUrl = null;
  let session = 0;
  let heardVoice = false;

  function setPhase(next, message) {
    phase = next;
    status.textContent = message;
    mic.classList.toggle("active", next !== "idle");
    mic.setAttribute("aria-pressed", String(next !== "idle"));
    mic.setAttribute("aria-label", next === "idle" ? "Iniciar conversa por voz" : "Conversa por voz ativa");
    document.getElementById("voiceTurnControls").classList.toggle("hidden", next === "idle");
    mic.disabled = next === "transcribing" || next === "researching" || next === "speaking" || state.running;
    stop.disabled = next === "idle" && !auto.checked;
  }

  function cleanMedia() {
    if (timer) { clearTimeout(timer); timer = null; }
    if (vadTimer) { clearInterval(vadTimer); vadTimer = null; }
    if (audioContext) { void audioContext.close().catch(() => {}); audioContext = null; }
    if (stream) { stream.getTracks().forEach(t => t.stop()); stream = null; }
    recorder = null;
  }

  function stopPlayback() {
    if (player) { player.pause(); player.src = ""; player = null; }
    if (audioUrl) { URL.revokeObjectURL(audioUrl); audioUrl = null; }
  }

  function stopSession() {
    session += 1;
    auto.checked = false;
    stopPlayback();
    if (recorder && recorder.state !== "inactive") recorder.stop();
    cleanMedia();
    setPhase("idle", "Conversa por voz parada. O microfone está desligado.");
  }

  function finishRecording() {
    if (recorder && recorder.state === "recording") {
      recorder.stop();
      setPhase("transcribing", "A processar a pergunta falada…");
    }
  }

  function startSilenceDetection(media, recorderInstance) {
    if (!auto.checked) return;
    try {
      const AudioCtx = window.AudioContext || window.webkitAudioContext;
      if (!AudioCtx) return;
      audioContext = new AudioCtx();
      const source = audioContext.createMediaStreamSource(media);
      const analyser = audioContext.createAnalyser();
      analyser.fftSize = 2048;
      source.connect(analyser);
      const sample = new Float32Array(analyser.fftSize);
      const startedAt = Date.now();
      let lastVoice = startedAt;
      heardVoice = false;
      vadTimer = window.setInterval(() => {
        if (recorderInstance.state !== "recording") return;
        analyser.getFloatTimeDomainData(sample);
        let power = 0;
        for (const value of sample) power += value * value;
        const rms = Math.sqrt(power / sample.length);
        if (rms > 0.019) { heardVoice = true; lastVoice = Date.now(); }
        if (heardVoice && Date.now() - lastVoice > 1500 && Date.now() - startedAt > 1200) {
          finishRecording();
        } else if (!heardVoice && Date.now() - startedAt > 12000) {
          finishRecording();
        }
      }, 120);
    } catch {
      // The user can always stop recording manually; no silent fallback to fake speech.
    }
  }

  async function speak(text, ticket) {
    if (ticket !== session) return;
    setPhase("speaking", "O FA_Agent está a responder em voz alta…");
    const spokenText = String(text || "").trim().slice(0, 1800);
    if (!spokenText) return;
    const response = await fetch("/api/speak-reply", {
      method: "POST", headers: {"Content-Type": "application/json"},
      body: JSON.stringify({text: spokenText}), cache: "no-store"
    });
    if (!response.ok) {
      let reason = "Não foi possível gerar áudio.";
      try { reason = (await response.json()).detail || reason; } catch {}
      throw Error(reason);
    }
    const blob = await response.blob();
    if (ticket !== session) return;
    audioUrl = URL.createObjectURL(blob);
    const current = new Audio(audioUrl);
    player = current;
    await new Promise((resolve, reject) => {
      current.onended = resolve;
      current.onerror = () => reject(Error("O navegador não conseguiu reproduzir o áudio."));
      current.play().catch(reject);
    });
    stopPlayback();
  }

  async function handleRecording(blob, ticket) {
    if (ticket !== session) return;
    if (blob.size < 350) {
      setPhase("idle", "Gravação demasiado curta. Tenta novamente.");
      auto.checked = false;
      return;
    }
    try {
      setPhase("transcribing", "A transcrever o áudio…");
      const mime = blob.type.split(";")[0] || "audio/webm";
      const transcription = await fetch("/api/voice/transcribe", {
        method: "POST", headers: {"Content-Type": mime}, body: blob,
        cache: "no-store"
      });
      if (!transcription.ok) {
        let reason = "Não foi possível transcrever a pergunta.";
        try { reason = (await transcription.json()).detail || reason; } catch {}
        throw Error(reason);
      }
      const {text} = await transcription.json();
      if (ticket !== session) return;
      if (!text || !text.trim()) throw Error("Não foi detetada uma pergunta.");
      document.getElementById("question").value = text.trim();
      // Follow-up synthesis uses the existing conversation history for the selected asset.
      if (state.capabilities?.llm_configured && document.getElementById("mode").value === "live") {
        document.getElementById("useLLM").checked = true;
      }
      setPhase("researching", "A consultar os agentes e as fontes…");
      const result = await submitQuery({preventDefault() {}});
      if (ticket !== session) return;
      if (!result || !result.answer) throw Error("A análise não devolveu uma resposta falada.");
      if (result.report?.request) {
        const selection = result.report.request;
        const symbol = document.getElementById("symbol");
        const assetClass = document.getElementById("assetClass");
        if (selection.symbol && selection.symbol !== "DEMO") symbol.value = selection.symbol;
        if (selection.asset_class) assetClass.value = selection.asset_class;
      }
      if (result.answer.length > 1800) {
        status.textContent = "Resposta oral abreviada. O texto integral permanece no chat.";
      }
      await speak(result.answer, ticket);
      if (ticket !== session) return;
      if (auto.checked) {
        setPhase("idle", "A preparar a pergunta seguinte…");
        await startRecording(ticket);
      } else {
        setPhase("idle", "Resposta concluída. Clica em Falar para continuar.");
      }
    } catch (error) {
      if (ticket !== session) return;
      auto.checked = false;
      stopPlayback();
      setPhase("idle", "Erro de áudio: " + String(error.message || error));
    }
  }

  async function startRecording(ticket) {
    if (ticket !== session || phase === "recording" || state.running || voiceBusy || voiceRecorder?.state === "recording") return;
    if (!window.MediaRecorder || !navigator.mediaDevices?.getUserMedia) {
      setPhase("idle", "O navegador não suporta gravação de áudio neste contexto.");
      auto.checked = false;
      return;
    }
    if (!state.capabilities?.voice?.available) {
      setPhase("idle", "Configura OPENAI_API_KEY (ou OPENAI_API_KEY_Demo) para áudio.");
      auto.checked = false;
      return;
    }
    let media = null;
    try {
      if (typeof stopSpeech === "function") stopSpeech();
      media = await navigator.mediaDevices.getUserMedia({audio: {
        echoCancellation: true, noiseSuppression: true, autoGainControl: true
      }});
      if (ticket !== session) {
        media.getTracks().forEach(track => track.stop());
        return;
      }
      stream = media;
      chunks = [];
      const mime = ["audio/webm;codecs=opus", "audio/webm", "audio/mp4"]
        .find(type => MediaRecorder.isTypeSupported(type));
      const current = mime ? new MediaRecorder(media, {mimeType: mime}) : new MediaRecorder(media);
      recorder = current;
      const captureType = current.mimeType || "audio/webm";
      current.ondataavailable = e => { if (e.data.size) chunks.push(e.data); };
      current.onerror = () => { auto.checked = false; stopSession(); };
      current.onstop = () => {
        const data = new Blob(chunks, {type: captureType});
        const didHear = heardVoice;
        const automatic = auto.checked;
        cleanMedia();
        if (ticket !== session) return;
        if (automatic && !didHear) {
          auto.checked = false;
          setPhase("idle", "Sem voz detetada. O microfone foi desligado.");
          return;
        }
        void handleRecording(data, ticket);
      };
      current.start(250);
      setPhase("recording", "A ouvir. Termina no botão ou após uma pausa em modo contínuo.");
      timer = window.setTimeout(finishRecording, 45000);
      startSilenceDetection(media, current);
    } catch {
      if (media) media.getTracks().forEach(t => t.stop());
      cleanMedia();
      auto.checked = false;
      setPhase("idle", "Não foi possível aceder ao microfone. Confirma as permissões do navegador.");
    }
  }

  mic.addEventListener("click", () => {
    if (phase === "recording") { finishRecording(); return; }
    if (phase !== "idle") return;
    const ticket = ++session;
    void startRecording(ticket);
  });
  stop.addEventListener("click", stopSession);
  auto.addEventListener("change", () => {
    if (!auto.checked && phase === "idle") setPhase("idle", "Modo contínuo desligado.");
    if (auto.checked && phase === "idle") status.textContent =
      "Clica em Falar para iniciar. A gravação termina automaticamente após uma pausa.";
  });
  document.getElementById("clearChat").addEventListener("click", stopSession);
  for (const id of ["symbol", "assetClass", "mode"]) {
    document.getElementById(id).addEventListener("change", stopSession);
  }
  window.FAVoiceDialogue = {
    active: () => phase !== "idle",
    stop: stopSession,
  };
  window.addEventListener("pagehide", stopSession);
  window.addEventListener("beforeunload", stopSession);
})();
