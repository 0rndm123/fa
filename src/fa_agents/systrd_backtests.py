"""Optional read-only SysTrd backtest specialist over a versioned HTTP API.

No PostgreSQL driver, credentials, SQL or SysTrd source code are needed in FA.
"""
from __future__ import annotations

import json
import os
import re
import unicodedata
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen

from .models import AgentResult, Evidence, FinancialObservation, ResearchRequest


def _normalized(text: str) -> str:
    s = unicodedata.normalize("NFKD", text.casefold())
    return "".join(c for c in s if not unicodedata.combining(c))


def is_backtest_question(question: str) -> bool:
    q = _normalized(question)
    return bool(re.search(
        r"\bbacktests?\b|\bbacktesting\b|\bbacktest_ops\b|"
        r"\bprofit factor\b|\bhistoric[oa] de operac(?:ao|oes)\b|"
        r"\bresultados? d[oe]s? (?:meus? )?backtests?\b",
        q,
    ))


def _timeframe(question: str) -> str | None:
    q = _normalized(question)
    if re.search(r"\b4\s*h\b|\b4\s*horas\b", q):
        return "4h"
    if re.search(r"\b(?:daily|diari[oa]|1d)\b|\bD\b", question):
        return "D"
    if re.search(r"\b(?:weekly|semanal|1w)\b|\bW\b", question):
        return "W"
    return None


class SysTrdAPI:
    def __init__(self, base_url: str, token: str | None = None):
        parsed = urlsplit(base_url.strip().rstrip("/"))
        if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.path not in {"", "/"}:
            raise ValueError("FA_SYSTRD_API_URL must be an HTTP(S) origin without a path.")
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError("FA_SYSTRD_API_URL cannot contain credentials, query or fragment.")
        if parsed.scheme == "http" and parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
            raise ValueError("Remote SysTrd API requires HTTPS.")
        self.base_url = base_url.strip().rstrip("/")
        self.token = token

    def get(self, endpoint: str, **filters):
        params = {k: v for k, v in filters.items() if v is not None}
        url = self.base_url + "/api/v1/backtests/" + endpoint
        if params:
            url += "?" + urlencode(params)
        headers = {"Accept": "application/json", "X-SysTrd-Channel": "agent"}
        if self.token:
            headers["Authorization"] = "Bearer " + self.token
        try:
            with urlopen(Request(url, headers=headers), timeout=10) as response:
                payload = response.read(1_000_001)
            if len(payload) > 1_000_000:
                raise ValueError("SysTrd response exceeds 1 MB limit.")
            return json.loads(payload), url
        except HTTPError as exc:
            if exc.code in {401, 403}:
                raise ValueError("SysTrd API rejected authentication or read permissions.") from exc
            raise ValueError(f"SysTrd API HTTP {exc.code} on {endpoint}.") from exc
        except (URLError, TimeoutError) as exc:
            raise ValueError("SysTrd API unreachable; check local service and FA_SYSTRD_API_URL.") from exc
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise ValueError("SysTrd API returned invalid JSON.") from exc


def backtest_specialist(request: ResearchRequest, services) -> AgentResult:
    if services.demo:
        return AgentResult(agent_id="backtest", status="no_data",
                           summary="SysTrd backtests require live mode, not synthetic demo.")
    url = os.getenv("FA_SYSTRD_API_URL", "").strip()
    if not url:
        return AgentResult(agent_id="backtest", status="no_data",
                           summary="SysTrd API is not connected.",
                           limitations=["Set FA_SYSTRD_API_URL to the local SysTrd API origin."])
    try:
        client = SysTrdAPI(url, os.getenv("FA_SYSTRD_ACCESS_TOKEN"))
        timeframe = _timeframe(request.question)
        scopes, scopes_url = client.get("scopes", symbol=request.symbol, timespan=timeframe)
        choices = list(scopes.get("items") or [])
        if request.exchange and request.exchange.isdecimal():
            choices = [r for r in choices if r["exchange_id"] == int(request.exchange)]
        configured_version = os.getenv("FA_SYSTRD_CALCULATOR_VERSION", "").strip()
        if configured_version:
            choices = [r for r in choices if r["calculator_version"] == configured_version]
        elif len(choices) > 1:
            # Only accept an explicit calculator version mentioned in the question.
            matching = [r for r in choices if str(r["calculator_version"]).lower() in
                        request.question.lower()]
            if matching:
                choices = matching
        if not choices:
            return AgentResult(agent_id="backtest", status="no_data",
                               summary=f"No backtest operations available for {request.symbol} in this scope.",
                               limitations=["Check exact symbol, exchange_id, timespan and calculator version."])
        if len(choices) != 1:
            labels = [
                f"exchange_id={r['exchange_id']} symbol={r['symbol']} "
                f"timespan={r['timespan']} version={r['calculator_version']}"
                for r in choices[:10]
            ]
            return AgentResult(agent_id="backtest", status="no_data",
                               summary="Multiple backtest scopes exist. Specify an exchange_id, "
                                       "timeframe and calculator version; nothing was combined.",
                               claims=labels,
                               limitations=["You can set FA_SYSTRD_CALCULATOR_VERSION for the pilot."])
        row = choices[0]
        filters = {
            "exchange_id": row["exchange_id"], "symbol": row["symbol"],
            "timespan": row["timespan"], "calculator_version": row["calculator_version"],
        }
        summary, source_url = client.get("summary", **filters)
        stats = summary["statistics"]
        operations, _ = client.get("operations", **filters, status="CLOSED", limit=100)
        observations = []
        for item in operations.get("items", []):
            if item.get("pnl_pct") is not None and item.get("exit_timestamp"):
                observations.append(FinancialObservation(
                    metric="trade_pnl_pct", period_end=str(item["exit_timestamp"]),
                    value=float(item["pnl_pct"]), unit="%",
                    source_id="systrd-trades",
                ))
        metrics = {key: float(val) if isinstance(val, (int, float)) else
                   float(val) if val is not None and key in
                   {"average_gross_pnl_pct", "gross_profit_pct_sum", "gross_loss_pct_sum",
                    "gross_return_ratio"} else None
                   for key, val in stats.items()}
        metrics.update({"exchange_id": row["exchange_id"],
                        "timespan": row["timespan"],
                        "calculator_version": row["calculator_version"]})
        limitations = list(summary.get("limitations") or [])
        limitations.append("Trade observations show at most the 100 most recent closed operations.")
        return AgentResult(
            agent_id="backtest", status="partial",
            summary=f"SysTrd returned {stats['events']} events for "
                    f"{row['symbol']} / exchange_id={row['exchange_id']} / {row['timespan']} "
                    f"/ {row['calculator_version']} ({summary['validation_status']}).",
            claims=[
                f"Closed events: {stats['closed_events']}; closed with PnL: {stats['closed_with_pnl']}.",
                "These results are not verified strategy performance or investment advice.",
            ],
            metrics=metrics, observations=observations,
            evidence=[Evidence(source_id="systrd-trades", source_name="SysTrd API read-only",
                               source_url=source_url, retrieved_at=datetime.now(timezone.utc),
                               text_excerpt=f"Scope discovery: {scopes_url}")],
            limitations=limitations,
        )
    except (ValueError, KeyError, TypeError) as exc:
        return AgentResult(agent_id="backtest", status="no_data",
                           summary=str(exc), limitations=["Check SysTrd API availability and scope."])


def backtest_answer(result: AgentResult) -> str:
    lines = [result.summary]
    if result.status == "partial":
        s = result.metrics
        for k in ("closed_events", "closed_with_pnl", "winning_trades", "losing_trades",
                  "average_gross_pnl_pct", "gross_return_ratio"):
            if s.get(k) is not None:
                lines.append(f"{k.replace('_', ' ')}: {s[k]}")
    elif result.claims:
        lines.extend(result.claims)
    if result.limitations:
        lines.append("Limitações: " + "; ".join(result.limitations[:3]))
    return "\n".join(lines)
