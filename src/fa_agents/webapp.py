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
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator

from .agents import Services
from .catalog import SPECIALISTS, choose_agents
from .graph import build_graph
from .llm import explain
from .models import AssetClass, ResearchReport, ResearchRequest
from .providers import ProviderError, prices_from_csv

WEB_DIR = Path(__file__).parent / "web"
app = FastAPI(title="FA Agent Research Workbench", version="0.3.0",
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
    return {
        "agents": [{"id": key, "description": value,
                    "implementation": ("working" if key in {"financial_data", "fundamental"} else
                        "partial" if key in {"filings", "news", "technical", "risk"} else "planned")}
                   for key, value in SPECIALISTS.items()],
        "classes": [cls.value for cls in AssetClass],
        "llm_configured": has_llm,
        "sec_configured": "@" in os.getenv("SEC_USER_AGENT", ""),
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


@app.post("/api/analyze")
def analyze(payload: AnalyzeInput):
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
        request = ResearchRequest(
            symbol=payload.symbol, asset_class=payload.asset_class,
            exchange=payload.exchange, question=payload.question,
            horizon=payload.horizon, include_agents=payload.agents,
        )
        selected = choose_agents(request)
        services = Services.build(payload.mode, str(path) if path else None)
        state = build_graph(services).invoke({"request": request.model_dump(mode="json")})
        report = ResearchReport.model_validate(state["report"])
        if payload.llm:
            # Context is untrusted text and only assists follow-up interpretation.
            context = [item.model_dump() for item in payload.history[-8:]]
            report.llm_commentary = explain(report, payload.model, history=context)
        answer = report.llm_commentary or _coverage_answer(report)
        return {"report": report.model_dump(mode="json"), "answer": answer,
                "selected_agents": selected}
    except (ValueError, RuntimeError, ProviderError, OSError) as exc:
        raise HTTPException(422, f"{type(exc).__name__}: {exc}") from exc


def _coverage_answer(report: ResearchReport) -> str:
    """Explicit non-LLM chat answer based on tool results, with no invented analysis."""
    lines = [report.summary]
    for item in report.results:
        if item.claims and item.status in {"completed", "partial"}:
            lines.append(f"{item.agent_id}: " + " ".join(item.claims[:3]))
    if report.warnings:
        lines.append("Limitations: " + "; ".join(report.warnings[:4]))
    if report.data_mode == "demo":
        lines.append("DEMO DATA: These are synthetic values, not real market information.")
    return "\n\n".join(lines)
