"""Local-only interactive research workbench API.

This is a prototype chat + structured-report application, NOT a public-hosted service.
Start with: python -m uvicorn fa_agents.webapp:app --host 127.0.0.1 --port 8300
"""
from __future__ import annotations

import os
import tempfile
import uuid
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, Response
from starlette.concurrency import run_in_threadpool
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator

from .agents import Services
from .catalog import SPECIALISTS, choose_agents, select_for_question
from .graph import build_graph
from .llm import explain
from .models import AssetClass, ResearchReport, ResearchRequest, AgentResult, Evidence
from .providers import ProviderError, prices_from_csv, sec_user_agent_config
from .market_data import MarketDataOrchestrator, is_price_question, extract_symbol, quote_answer
from .voice import (
    MAX_AUDIO_BYTES, MAX_SPEECH_CHARS, VoiceTranscriptionError,
    transcribe_audio, transcription_configured, synthesize_speech,
)

WEB_DIR = Path(__file__).parent / "web"
app = FastAPI(title="FA Agent Research Workbench", version="0.6.0",
              docs_url=None, redoc_url=None, openapi_url=None)
app.mount("/static", StaticFiles(directory=str(WEB_DIR)), name="static")
_tmp = tempfile.TemporaryDirectory(prefix="fa_agent_web_")
_uploaded_prices: dict[str, Path] = {}


@app.middleware("http")
async def local_only(request: Request, call_next):
    """Require loopback requests, and same-origin for browser API mutations."""
    from fastapi.responses import JSONResponse
    client = request.client.host if request.client else None
    if client not in {"127.0.0.1", "::1", "testclient"}:
        return JSONResponse(status_code=403, content={"detail": "Localhost access only."})
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        origin = request.headers.get("origin")
        if origin:
            from urllib.parse import urlsplit
            parsed = urlsplit(origin)
            host = request.url.hostname
            if parsed.scheme not in {"http", "https"} or parsed.hostname != host or parsed.port != request.url.port:
                return JSONResponse(status_code=403, content={"detail": "Origin not allowed."})
    return await call_next(request)


class SpeakInput(BaseModel):
    text: str = Field(min_length=1, max_length=MAX_SPEECH_CHARS)


class HistoryItem(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(max_length=2000)


class AnalyzeInput(BaseModel):
    symbol: str = Field(default="DEMO", min_length=1, max_length=50)
    asset_class: AssetClass = AssetClass.EQUITY
    exchange: str | None = Field(default=None, max_length=100)
    question: str = Field(default="Analyze this asset.", min_length=1, max_length=6000)
    horizon: Literal["short", "medium", "long"] = "medium"
    mode: Literal["demo", "live"] = "demo"
    agents: list[str] | None = Field(default=None, max_length=20)
    llm: bool = False
    model: str | None = Field(default=None, max_length=100)
    price_upload_id: str | None = None
    cot_market_code: str | None = Field(default=None, max_length=12)
    cot_report_type: Literal["tff","disaggregated","legacy"] | None = None
    history: list[HistoryItem] = Field(default_factory=list, max_length=8)

    @field_validator("symbol")
    @classmethod
    def upper_symbol(cls, value: str) -> str:
        return value.strip().upper()


@app.get("/")
def index():
    return FileResponse(WEB_DIR / "index.html")


@app.get("/api/capabilities")
def capabilities():
    from .llm import resolve_api_key
    try:
        resolve_api_key()
        has_llm = True
    except ValueError:
        has_llm = False
    _sec_value, sec_source = sec_user_agent_config()
    return {
        "agents": [{"id": key, "description": value,
                    "implementation": ("working" if key in {"financial_data", "fundamental", "financial_performance"} else
                        "partial" if key in {"filings", "news", "technical", "risk", "debt_liquidity", "governance", "industry_context", "competition", "cot", "crypto_derivatives"} else "planned")}
                   for key, value in SPECIALISTS.items()],
        "classes": [cls.value for cls in AssetClass],
        "cot_reports": ["tff","disaggregated","legacy"],
        "cot_source": os.getenv("FA_COT_SOURCE","cftc"),
        "llm_configured": has_llm,
        "sec_configured": bool(_sec_value),
        "sec_config_source": sec_source,
        "quote_providers": [
            {"id":"yahoo","status":"available_unofficial"},
            {"id":"binance","status":"available_official"},
            {"id":"tradingview","status":"adapter_configured" if os.getenv("FA_TRADINGVIEW_QUOTE_ADAPTER_URL") else "adapter_not_configured"},
        ],
        "voice_transcription_configured": transcription_configured(),
        "voice_replies_configured": transcription_configured(),
        "mode": "local_only",
    }


@app.post("/api/upload-prices")
async def upload_prices(file: UploadFile = File(...)):
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(400, "Only CSV files are accepted.")
    data = await file.read(2_000_001)
    await file.close()
    if len(data) > 2_000_000:
        raise HTTPException(413, "Price CSV must be smaller than 2 MB.")
    identifier = uuid.uuid4().hex
    path = Path(_tmp.name) / f"{identifier}.csv"
    path.write_bytes(data)
    try:
        observations = prices_from_csv(str(path))
        if not observations:
            raise ProviderError("No dated prices found.")
    except (ProviderError, ValueError, UnicodeError) as exc:
        path.unlink(missing_ok=True)
        raise HTTPException(400, str(exc)) from exc
    _uploaded_prices[identifier] = path
    return {"upload_id": identifier, "observations": len(observations),
            "first_date": observations[0][0], "last_date": observations[-1][0]}


@app.post("/api/transcribe-audio")
async def transcribe_voice(file: UploadFile = File(...)):
    """Explicit audio upload -> transcription; never automatically execute research."""
    try:
        audio = await file.read(MAX_AUDIO_BYTES + 1)
    finally:
        await file.close()
    if not audio:
        raise HTTPException(status_code=400, detail="Empty voice recording.")
    if len(audio) > MAX_AUDIO_BYTES:
        raise HTTPException(status_code=413, detail="Voice recording exceeds 10 MB.")
    try:
        transcript = transcribe_audio(audio, file.content_type)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except VoiceTranscriptionError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {"text": transcript, "requires_review": True}


@app.post("/api/speak-reply")
async def speak_reply(body: SpeakInput):
    """Opt-in playback of an answer; no research execution or audio persistence."""
    try:
        audio = await run_in_threadpool(synthesize_speech, body.text)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except VoiceTranscriptionError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return Response(content=audio, media_type="audio/mpeg", headers={"Cache-Control": "no-store"})


@app.post("/api/analyze")
def analyze(payload: AnalyzeInput):
    if is_price_question(payload.question):
        return _answer_market_quote(payload)
    if payload.mode == "demo" and payload.symbol != "DEMO":
        raise HTTPException(400, "Demo mode accepts only the synthetic DEMO asset.")
    if payload.mode == "demo" and payload.llm:
        raise HTTPException(400, "LLM commentary is disabled for synthetic demo data.")
    if payload.agents is not None and any(agent not in SPECIALISTS for agent in payload.agents):
        raise HTTPException(400, "Unknown agent in selection.")
    if payload.llm:
        from .llm import resolve_api_key
        try:
            resolve_api_key()
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
    path = None
    if payload.price_upload_id:
        path = _uploaded_prices.get(payload.price_upload_id)
        if path is None or not path.is_file():
            raise HTTPException(404, "Price upload not found. Upload the file again.")
    try:
        from .cot import is_cot_question
        resolved_symbol, resolved_class = (extract_symbol(
            payload.question, payload.symbol, payload.asset_class.value)
            if payload.mode == "live" and not is_cot_question(payload.question)
            else (payload.symbol, payload.asset_class.value))
        request = ResearchRequest(
            symbol=resolved_symbol, asset_class=resolved_class,
            exchange=payload.exchange, question=payload.question,
            horizon=payload.horizon, include_agents=payload.agents,
            cot_market_code=payload.cot_market_code,
            cot_report_type=payload.cot_report_type,
        )
        selected = select_for_question(request)
        request = request.model_copy(update={"include_agents": selected})
        services = Services.build(payload.mode, str(path) if path else None)
        state = build_graph(services).invoke({"request": request.model_dump(mode="json")})
        report = ResearchReport.model_validate(state["report"])
        if payload.llm:
            # Context is untrusted text and only assists follow-up interpretation.
            context = [item.model_dump() for item in payload.history[-8:]]
            report.llm_commentary = explain(report, payload.model, history=context)
        from .cot import cot_answer
        cot_record = next((x for x in report.results if x.agent_id == "cot"),None)
        from .crypto_derivatives import crypto_answer
        crypto_record = next((x for x in report.results if x.agent_id == "crypto_derivatives"),None)
        answer = report.llm_commentary or (
            cot_answer(cot_record) if cot_record else
            crypto_answer(crypto_record) if crypto_record else _coverage_answer(report))
        return {"report": report.model_dump(mode="json"), "answer": answer,
                "selected_agents": selected}
    except (ValueError, RuntimeError, ProviderError, OSError) as exc:
        raise HTTPException(422, f"{type(exc).__name__}: {exc}") from exc


def _coverage_answer(report: ResearchReport) -> str:
    """Explicit non-LLM chat answer based on tool results, with no invented analysis."""
    lines = [report.summary]
    for item in report.results:
        if item.status in {"completed", "partial"}:
            facts = []
            for name, value in item.metrics.items():
                if name in {"company", "sector_description", "sic"} or name.endswith("_period"):
                    continue
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    facts.append(f"{name.replace('_',' ')} = {value:,.3f}")
            if facts or item.claims:
                lines.append(f"{item.agent_id}: " + "; ".join(facts[:8])+
                             (". " if facts else "") + " ".join(item.claims[:3]))
            elif item.summary:
                lines.append(f"{item.agent_id}: {item.summary}")
            if item.agent_id in {"governance","competition","industry_context"} and item.limitations:
                lines.append(item.agent_id+" — "+item.limitations[0])
    if report.warnings:
        lines.append("Limitations: " + "; ".join(report.warnings[:4]))
    if report.data_mode == "demo":
        lines.append("DEMO DATA: These are synthetic values, not real market information.")
    return "\n\n".join(lines)


def _answer_market_quote(payload: AnalyzeInput):
    """Route a simple price question to provider specialists, not the full FA graph."""
    if payload.mode == "demo":
        raise HTTPException(400, "Cotação real requer modo Live. Selecione Live antes de perguntar.")
    try:
        ticker, asset_class = extract_symbol(
            payload.question, payload.symbol, payload.asset_class.value
        )
        comparison = MarketDataOrchestrator().get_quote(ticker, asset_class)
        reports=[]
        for attempt in comparison.attempts:
            if attempt.quote:
                quote = attempt.quote
                reports.append(AgentResult(
                    agent_id="quote_" + attempt.provider, status="completed",
                    summary=f"{quote.instrument}, {quote.venue}: {quote.price} {quote.currency}"
                            f" ({quote.at.isoformat()})",
                    metrics={
                        "price": quote.price, "currency": quote.currency, "symbol": quote.symbol,
                        "venue": quote.venue, "quote_time": quote.at.isoformat(),
                    },
                    evidence=[Evidence(
                        source_id="quote-" + attempt.provider + "-" + quote.symbol,
                        source_name=attempt.provider, source_url=quote.source_url,
                        retrieved_at=quote.retrieved_at, observed_at=quote.at,
                        text_excerpt=quote.caveat,
                    )],
                    limitations=[quote.caveat],
                ))
            else:
                reports.append(AgentResult(
                    agent_id="quote_" + attempt.provider, status="failed",
                    summary=f"{attempt.provider} did not return a usable market quote.",
                    limitations=[attempt.error or "No quote available."],
                ))
        request=ResearchRequest(
            symbol=ticker, asset_class=asset_class, question=payload.question,
            horizon=payload.horizon,
        )
        selected=comparison.selected
        report=ResearchReport(
            request=request, status=("partial" if selected and len(reports)>1 and any(
                r.status!="completed" for r in reports) else "completed" if selected else "not_ready"),
            data_mode="live", planned_agents=[r.agent_id for r in reports], results=reports,
            market_quote=comparison,
            summary=(f"Latest available quote from {selected.provider.upper()} for "
                     f"{selected.symbol}; other provider attempts shown separately."
                     if selected else f"No usable quote from configured market sources for {ticker}."),
            warnings=[r.summary for r in reports if r.status=="failed"],
        )
        return {"report":report.model_dump(mode="json"),
                "answer":quote_answer(comparison),
                "selected_agents":report.planned_agents}
    except (ProviderError, ValueError, RuntimeError) as exc:
        raise HTTPException(422, str(exc)) from exc
