"""Dedicated read-only crypto derivatives analyst.

Binance USD-M perpetual only. CFTC COT analysis is handled separately by cot.py.
No authenticated endpoints, orders, user accounts, or unsupported cross-exchange
aggregations. The source protocol permits a future independently managed PG DB.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from math import isfinite
from typing import Protocol
from urllib.parse import urlencode

from .models import AgentResult, Evidence, CryptoDerivativesData, CryptoMetricPoint
from .providers import ProviderError, fetch_bytes, now

VALID_PAIR = re.compile(r"^[A-Z0-9]{2,20}USDT$")
SUPPORTED_BASE = {"BTC", "ETH", "SOL", "BNB", "XRP", "ADA", "DOGE", "LINK", "AVAX"}

def resolve_pair(symbol: str) -> str:
    """Restrict to established, explicitly mapped Binance USD-M perpetual pairs.

    Exchange support is verified by Binance's response, not inferred from
    an asset being available for spot trading.
    """
    value = symbol.strip().upper()
    if value.endswith("-USD"):
        value = value[:-4]
    if value.endswith("USDT"):
        value = value[:-4]
    if value not in SUPPORTED_BASE:
        raise ProviderError(
            f"Crypto derivatives mapping not available for {symbol!r}. "
            "Choose a supported perpetual contract symbol, for example BTCUSDT."
        )
    return value + "USDT"


def _number(value, *, positive: bool = False, allow_negative: bool = False) -> float:
    try:
        value = float(value)
    except (ValueError, TypeError) as exc:
        raise ProviderError("Market provider returned a nonnumeric metric.") from exc
    if not isfinite(value) or (positive and value <= 0) or (not positive and not allow_negative and value < 0):
        raise ProviderError("Market provider returned an invalid metric.")
    return value


def _date_ms(value) -> datetime:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ProviderError("Missing Binance timestamp.")
    at = datetime.fromtimestamp(value / 1000, tz=timezone.utc)
    if at > now():
        raise ProviderError("Binance timestamp is in the future.")
    return at


class CryptoDerivativesSource(Protocol):
    def read_funding(self, pair: str, limit: int = 50) -> list[dict]: ...
    def read_open_interest(self, pair: str) -> dict: ...
    def read_long_short_accounts(self, pair: str, limit: int = 30) -> list[dict]: ...


class BinanceUsdmSource:
    """Official public USDⓈ-M endpoints; does not require an account or API key."""
    name = "binance_usdm"
    root = "https://fapi.binance.com"

    def __init__(self, loader=None):
        self.loader = loader

    def _fetch(self, endpoint: str, params: dict):
        url = self.root + endpoint + "?" + urlencode(params)
        raw = self.loader(url) if self.loader else fetch_bytes(
            url, "FA-Agent/0.7 read-only market research"
        )
        try:
            payload = json.loads(raw)
        except (TypeError, ValueError, UnicodeDecodeError) as exc:
            raise ProviderError("Invalid Binance Futures JSON.") from exc
        if isinstance(payload, dict) and ("code" in payload and "msg" in payload):
            raise ProviderError(f"Binance Futures rejected request: {payload.get('msg')}")
        return payload

    def read_funding(self, pair: str, limit: int = 50) -> list[dict]:
        if not VALID_PAIR.fullmatch(pair) or not 2 <= limit <= 100:
            raise ProviderError("Invalid Binance funding request.")
        data = self._fetch("/fapi/v1/fundingRate", {"symbol": pair, "limit": limit})
        if not isinstance(data, list):
            raise ProviderError("Invalid funding history structure.")
        return data

    def read_open_interest(self, pair: str) -> dict:
        if not VALID_PAIR.fullmatch(pair):
            raise ProviderError("Invalid open interest contract.")
        data = self._fetch("/fapi/v1/openInterest", {"symbol": pair})
        if not isinstance(data, dict):
            raise ProviderError("Invalid open interest response.")
        return data

    def read_long_short_accounts(self, pair: str, limit: int = 30) -> list[dict]:
        if not VALID_PAIR.fullmatch(pair) or not 2 <= limit <= 30:
            raise ProviderError("Invalid account-ratio request.")
        data = self._fetch("/futures/data/globalLongShortAccountRatio",
                           {"symbol": pair, "period": "1d", "limit": limit})
        if not isinstance(data, list):
            raise ProviderError("Invalid global account ratio response.")
        return data


def _validate_history(rows, pair, value_key, time_key, metric_name,
                      unit, factor=1.0) -> list[CryptoMetricPoint]:
    points = {}
    for row in rows:
        try:
            if row.get("symbol") != pair:
                raise ProviderError(f"Provider returned wrong pair for {metric_name}.")
            at = _date_ms(int(row[time_key]))
            value = _number(row[value_key], allow_negative=(metric_name=="funding_rate_pct")) * factor
            if at in points:
                raise ProviderError(f"Duplicate {metric_name} observation.")
            points[at] = CryptoMetricPoint(
                metric=metric_name, at=at, value=round(value, 10), unit=unit
            )
        except (ValueError, TypeError, KeyError) as exc:
            raise ProviderError(f"Invalid {metric_name} row: {exc}") from exc
    return [points[t] for t in sorted(points)]


def research_crypto_derivatives(request, svc, source:CryptoDerivativesSource | None=None) -> AgentResult:
    if request.asset_class.value != "crypto":
        return AgentResult(agent_id="crypto_derivatives", status="no_data",
            summary="Crypto derivative research requires a crypto instrument.",
            limitations=["Use a crypto symbol like BTC, ETH or BTCUSDT."])
    if svc.demo:
        return AgentResult(agent_id="crypto_derivatives", status="no_data",
            summary="Demo does not provide fictional leveraged positions.",
            limitations=["Select Live for source-backed Binance USD-M derivatives data."])
    pair = resolve_pair(request.symbol)
    provider = source if source is not None else BinanceUsdmSource()
    warnings=[]
    readings={}
    urls={
        "funding_rate_pct":"https://fapi.binance.com/fapi/v1/fundingRate?"+urlencode({"symbol":pair,"limit":50}),
        "open_interest":"https://fapi.binance.com/fapi/v1/openInterest?"+urlencode({"symbol":pair}),
        "global_long_short_account_ratio":"https://fapi.binance.com/futures/data/globalLongShortAccountRatio?"+
                                          urlencode({"symbol":pair,"period":"1d","limit":30}),
    }
    # Each metric may fail independently. Never fabricate absent measurements.
    try:
        readings["funding_rate_pct"]=_validate_history(
            provider.read_funding(pair,50),pair,"fundingRate","fundingTime",
            "funding_rate_pct","%",100.0,
        )
    except (ProviderError, KeyError, TypeError, ValueError, OSError) as exc:
        warnings.append("Funding history: "+str(exc))
    try:
        oi=provider.read_open_interest(pair)
        if oi.get("symbol")!=pair:
            raise ProviderError("Open interest instrument mismatch.")
        count=_number(oi.get("openInterest"),positive=True)
        reading=CryptoMetricPoint(metric="open_interest",at=_date_ms(int(oi["time"])),
                                  value=count,unit=pair.removesuffix("USDT"))
        readings["open_interest"]=[reading]
    except (ProviderError, KeyError, TypeError, ValueError, OSError) as exc:
        warnings.append("Open interest: "+str(exc))
    try:
        readings["global_long_short_account_ratio"]=_validate_history(
            provider.read_long_short_accounts(pair,30),pair,"longShortRatio",
            "timestamp","global_long_short_account_ratio","ratio",
        )
    except (ProviderError, KeyError, TypeError, ValueError, OSError) as exc:
        warnings.append("Global long/short accounts: "+str(exc))

    series=[p for records in readings.values() for p in records]
    if not series:
        return AgentResult(agent_id="crypto_derivatives",status="no_data",
            summary=f"No Binance USD-M derivatives data available for {pair}.",
            limitations=warnings or ["Market data feed returned no observations."])
    data=CryptoDerivativesData(
        provider="Binance USD-M Futures",
        instrument=pair,
        market_type="perpetual_usdm",
        series=series,
        retrieved_at=now(),
    )
    metrics:dict[str,float|str|None]={"venue":"Binance USD-M Futures",
                                     "instrument":pair,"contract_type":"PERPETUAL"}
    claims=[]
    evidence=[]
    for name,records in readings.items():
        if not records:continue
        latest=records[-1]
        metrics[name]=latest.value
        metrics[name+"_time_utc"]=latest.at.isoformat()
        explanation={
            "funding_rate_pct":"settled funding rate, percent per funding interval",
            "open_interest":"current outstanding contracts in base-asset units",
            "global_long_short_account_ratio":"ratio of long to short accounts, NOT positions",
        }[name]
        claims.append(f"{name}: {latest.value:g} {latest.unit}, "
                      f"reported at {latest.at.isoformat()} ({explanation}).")
        evidence.append(Evidence(
            source_id=f"binance-usdm-{pair}-{name}-{int(latest.at.timestamp())}",
            source_name="Binance USD-M Futures public market data",
            source_url=urls[name],retrieved_at=now(),observed_at=latest.at,
            text_excerpt=explanation,
        ))
    return AgentResult(
        agent_id="crypto_derivatives",
        status="partial" if warnings else "completed",
        summary=f"Binance USD-M perpetual derivatives metrics for {pair}, "
                f"with {len(series)} timestamped readings.",
        metrics=metrics,claims=claims,evidence=evidence,
        crypto_derivatives=data,
        limitations=[
            "These are Binance USD-M perpetual contracts only, not consolidated crypto-market positions.",
            "Funding observations are settlement rates per funding interval, not annualised yields.",
            "Open interest is in base asset units; do not label it USD without a contemporaneous conversion.",
            "Global long/short ratio counts accounts, not contracts or directional notional exposure.",
            "Funding/OI/account ratios are not CFTC COT categories and must not be merged.",
            *warnings,
        ],
    )


DERIVATIVES_TERMS = {
    "funding", "fundingrate", "perpetuo", "perpetuos", "perpetual", "perpetuals",
    "derivados", "derivatives", "leverage", "alavancagem", "liquidacoes",
    "liquidations", "oi", "posicionamento", "openinterest", "longshort",
}


def is_derivatives_question(question: str) -> bool:
    import unicodedata
    text=unicodedata.normalize("NFKD",question.casefold())
    text="".join(char for char in text if not unicodedata.combining(char))
    terms=set(re.findall(r"[a-z]+",text))
    if "cot" in terms or "commitments of traders" in text:
        return False
    if "open interest" in text or "long short" in text or "long/short" in text:
        return True
    return bool(terms & DERIVATIVES_TERMS)


def crypto_answer(result: AgentResult) -> str:
    if not result.crypto_derivatives:
        return result.summary+"\n"+" ".join(result.limitations[:2])
    m=result.metrics
    lines=[result.summary]
    labels=[
        ("funding_rate_pct","Funding liquidado"),
        ("open_interest","Open interest"),
        ("global_long_short_account_ratio","Rácio long/short de contas"),
    ]
    for key,label in labels:
        if key not in m:continue
        stamp=m.get(key+"_time_utc","")
        unit="%" if key=="funding_rate_pct" else (
            result.crypto_derivatives.instrument.removesuffix("USDT")
            if key=="open_interest" else "rácio")
        lines.append(f"{label}: {m[key]:,.6g} {unit} (referência {stamp}).")
    lines.append("Fonte: Binance USD-M Futures; contratos perpétuos, não posições COT.")
    if result.status=="partial":
        lines.append("Algumas métricas não puderam ser obtidas; consulte as limitações.")
    return "\n".join(lines)
