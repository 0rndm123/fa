"""Read-only provider-specific market-data agents and quotation orchestrator.

Yahoo Finance chart is unofficial. Binance Spot is official market-data-only.
TradingView Advanced Charts does not supply quote data: its specialist requires
an explicitly configured independent local adapter and never scrapes a login.
"""
from __future__ import annotations

import json
import os
import re
import unicodedata
from datetime import datetime, timezone
from math import isfinite
from urllib.parse import quote, urlencode, urlparse

from .models import MarketQuote, ProviderAttempt, QuoteResult, PricePoint
from .providers import ProviderError, fetch_bytes, now


def _positive(x) -> bool:
    try:
        return x is not None and isfinite(float(x)) and float(x) > 0
    except (TypeError, ValueError):
        return False


def _utc_unix(value, unit="seconds") -> datetime:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ProviderError("Market timestamp missing or invalid.")
    timestamp = float(value) / (1000 if unit == "milliseconds" else 1)
    stamp = datetime.fromtimestamp(timestamp, timezone.utc)
    if stamp > now():
        raise ProviderError("Market timestamp is in the future.")
    return stamp


def _currency(symbol: str) -> str:
    if symbol.endswith("USDT"):
        return "USDT"
    if symbol.endswith("USDC"):
        return "USDC"
    if symbol.endswith("FDUSD"):
        return "FDUSD"
    if symbol.endswith("BTC"):
        return "BTC"
    return "USD"


def _norm(text: str) -> str:
    d = unicodedata.normalize("NFKD", text.casefold())
    return "".join(char for char in d if not unicodedata.combining(char))


_ALIASES = {
    "nvidia": "NVDA", "nvda": "NVDA", "apple": "AAPL", "aapl": "AAPL",
    "microsoft": "MSFT", "msft": "MSFT", "tesla": "TSLA", "tsla": "TSLA",
    "google": "GOOGL", "alphabet": "GOOGL", "googl": "GOOGL",
    "amazon": "AMZN", "amzn": "AMZN", "palantir": "PLTR", "pltr": "PLTR",
    "bitcoin": "BTC", "btc": "BTC", "ethereum": "ETH", "eth": "ETH",
    "solana": "SOL", "sol": "SOL",
}
_REQUEST_WORDS = {"price", "quote", "stock", "last", "current", "today", "preco",
                  "cotacao", "cotacoes", "quanto", "qual", "hoje", "agora", "atual",
                  "acao", "acoes", "empresa", "valor", "ticker", "the", "what", "is"}
_Q_RE = re.compile(
    r"\b(preco|cotacao|cotacoes|price|quote|trading at|quanto custa|"
    r"quanto vale|quanto esta a valer|what is .* trading at)\b"
)
_NONSPOT = re.compile(
    r"\b(preco alvo|preco justo|price target|target price|fair value|"
    r"valuation|avaliacao|evolucao|historico|historica|desde|ultimo mes|"
    r"previsao|forecast|projecao)\b"
)


def is_price_question(question: str) -> bool:
    normalized = _norm(question)
    return bool(_Q_RE.search(normalized)) and not bool(_NONSPOT.search(normalized))


def extract_symbol(question: str, current_symbol: str, asset_class: str) -> tuple[str, str]:
    """Resolve explicit company names/finance tickers before the selected UI symbol."""
    normalized = _norm(question)
    tokens = set(re.findall(r"\b[a-z][a-z0-9]+\b", normalized))
    for name, symbol in _ALIASES.items():
        if name in tokens:
            return symbol, "crypto" if symbol in {"BTC", "ETH", "SOL"} else "equity"
    # Only uppercase candidate tokens to avoid treating Portuguese words as tickers.
    candidates = re.findall(r"(?<![\w])\$?([A-Z][A-Z0-9.^=_-]{1,11})(?![\w])", question)
    for candidate in candidates:
        if candidate.casefold() not in _REQUEST_WORDS and candidate not in {"USD", "EUR", "USDT", "ETF"}:
            return candidate, asset_class
    current_symbol = current_symbol.strip().upper()
    if current_symbol == "DEMO":
        raise ProviderError("Para consultar preços reais, selecione Live e indique um ticker, como NVDA.")
    if not re.fullmatch(r"[A-Z0-9^][A-Z0-9.^=_-]{0,24}", current_symbol):
        raise ProviderError("Ticker inválido.")
    return current_symbol, asset_class


def pairs_for_asset(symbol: str, asset_class: str) -> dict[str, str]:
    symbol = symbol.upper().strip()
    if asset_class == "crypto":
        base = symbol
        if base.endswith("-USD"):
            base = base[:-4]
        elif base.endswith("USDT"):
            base = base[:-4]
        if not re.fullmatch(r"[A-Z0-9]{2,16}", base):
            raise ProviderError("Unsupported crypto ticker.")
        return {"binance": base + "USDT", "yahoo": base + "-USD", "tradingview": "BINANCE:" + base + "USDT"}
    return {"yahoo": symbol, "tradingview": symbol}


class YahooQuoteAgent:
    id = "yahoo"

    def __init__(self, loader=None):
        self.loader = loader

    def fetch(self, symbol: str) -> MarketQuote:
        if not re.fullmatch(r"[A-Z0-9^][A-Z0-9.^=_-]{0,24}", symbol):
            raise ProviderError("Invalid Yahoo symbol.")
        url = "https://query1.finance.yahoo.com/v8/finance/chart/" + quote(symbol, safe="")
        url += "?interval=1h&range=5d"
        raw = self.loader(url) if self.loader else fetch_bytes(
            url, "Mozilla/5.0 (compatible; FA-Agent/0.4 local research)"
        )
        try:
            chart = json.loads(raw)["chart"]
            if chart.get("error"):
                raise ProviderError("Yahoo rejected instrument: " + str(chart["error"]))
            item = chart["result"][0]
            meta = item["meta"]
            actual = str(meta["symbol"]).upper()
            if actual != symbol:
                raise ProviderError(f"Wrong Yahoo instrument: {actual}")
            value = meta.get("regularMarketPrice")
            stamp = meta.get("regularMarketTime")
            if not _positive(value):
                raise ProviderError("Yahoo did not return a valid market price.")
            if stamp is None:
                raise ProviderError("Yahoo market quote has no timestamp.")
            currency = str(meta.get("currency", "")).upper()
            if not re.fullmatch(r"[A-Z]{3}", currency):
                raise ProviderError("Yahoo currency missing.")
            dt = _utc_unix(stamp)
            previous = meta.get("chartPreviousClose", meta.get("previousClose"))
            previous = float(previous) if _positive(previous) else None
            history=[]
            try:
                bars=item.get("indicators",{}).get("quote",[{}])[0].get("close",[])
                for t, price in zip(item.get("timestamp",[]),bars):
                    if _positive(price) and t<=stamp:
                        history.append(PricePoint(at=_utc_unix(t),price=float(price)))
            except (TypeError, ValueError, KeyError):
                history=[]
            return MarketQuote(
                provider=self.id, symbol=actual,
                instrument=str(meta.get("longName") or meta.get("shortName") or actual),
                venue=str(meta.get("fullExchangeName") or meta.get("exchangeName") or "Unspecified"),
                currency=currency, price=float(value), at=dt, retrieved_at=now(),
                timestamp_kind="regular_market_quote", history=history[-120:],
                previous_close=previous,
                source_url="https://finance.yahoo.com/quote/"+quote(symbol,safe="")+"/",
                caveat="Unofficial Yahoo chart endpoint; feed delay and live status not verified.",
            )
        except (IndexError, TypeError, KeyError, ValueError) as exc:
            raise ProviderError(f"Invalid Yahoo quote payload: {exc}") from exc


class BinanceSpotQuoteAgent:
    id = "binance"

    def __init__(self, loader=None):
        self.loader = loader

    def fetch(self, symbol: str) -> MarketQuote:
        if not re.fullmatch(r"[A-Z0-9]{4,25}", symbol):
            raise ProviderError("Invalid Binance spot pair.")
        url = "https://data-api.binance.vision/api/v3/ticker/24hr?" + urlencode({"symbol":symbol})
        raw = self.loader(url) if self.loader else fetch_bytes(url, "FA-Agent/0.4 research read-only")
        try:
            data = json.loads(raw)
            if data.get("symbol") != symbol:
                raise ProviderError("Binance did not confirm the requested spot pair.")
            value = data["lastPrice"]
            if not _positive(value):
                raise ProviderError("Binance returned an invalid last price.")
            # closeTime is the rolling-window snapshot end, NOT necessarily the last trade time.
            at = _utc_unix(data["closeTime"], "milliseconds")
            prev24 = data.get("prevClosePrice")
            prev24 = float(prev24) if _positive(prev24) else None
            return MarketQuote(
                provider=self.id, symbol=symbol, instrument=symbol,
                venue="Binance Spot", currency=_currency(symbol), price=float(value),
                at=at, retrieved_at=now(), timestamp_kind="rolling_24h_window_end",
                previous_close=prev24,
                source_url="https://www.binance.com/en/trade/"+quote(symbol[:-4],safe="")+"_USDT"
                if symbol.endswith("USDT") else "https://www.binance.com/en/markets",
                caveat="24-hour rolling window. closeTime is the window end, not verified last-trade time.",
            )
        except (KeyError, ValueError, TypeError) as exc:
            raise ProviderError(f"Invalid Binance quote payload: {exc}") from exc


class TradingViewQuoteAgent:
    id = "tradingview"

    def __init__(self, loader=None, adapter_url: str | None = None):
        self.loader = loader
        self.adapter_url = adapter_url if adapter_url is not None else os.getenv("FA_TRADINGVIEW_QUOTE_ADAPTER_URL","")

    def fetch(self, symbol: str) -> MarketQuote:
        """Read from an explicitly configured local authorized adapter; no scraping."""
        if not self.adapter_url:
            raise ProviderError("TradingView connection not configured. The official charting datafeed is not a public quote API.")
        parsed = urlparse(self.adapter_url)
        if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1","localhost"}:
            raise ProviderError("TradingView adapter must run on localhost; remote arbitrary URLs are blocked.")
        url=self.adapter_url.rstrip("/")+"/quote?"+urlencode({"symbol":symbol})
        raw=self.loader(url) if self.loader else fetch_bytes_local(url)
        try:
            data=json.loads(raw)
            # The adapter must declare the actual instrument, market, currency and source timestamp.
            if data["symbol"] != symbol:
                raise ProviderError("TradingView adapter returned a different symbol.")
            if not _positive(data["price"]) or not re.fullmatch(r"[A-Z]{3,5}",data["currency"]):
                raise ProviderError("TradingView adapter returned invalid price or currency.")
            at=datetime.fromisoformat(data["quote_time"].replace("Z","+00:00"))
            if at.tzinfo is None:
                raise ProviderError("TradingView quote timestamp must include its UTC offset.")
            at=at.astimezone(timezone.utc)
            if at>now():
                raise ProviderError("TradingView adapter timestamp is in the future.")
            return MarketQuote(
                provider=self.id, symbol=symbol,
                instrument=str(data.get("name") or symbol),
                venue=str(data["exchange"]), currency=data["currency"],
                price=float(data["price"]), at=at, retrieved_at=now(),
                timestamp_kind="adapter_reported", source_url=url,
                caveat="Quote supplied by configured independent local adapter; verify its original market-data licence.",
            )
        except (KeyError, ValueError, TypeError, AttributeError) as exc:
            raise ProviderError(f"Invalid TradingView adapter response: {exc}") from exc


def fetch_bytes_local(url: str) -> bytes:
    from urllib.request import urlopen, Request
    from urllib.error import URLError
    try:
        req=Request(url,headers={"Accept":"application/json"})
        with urlopen(req,timeout=7) as response:
            return response.read(300_001)
    except (URLError,OSError,TimeoutError) as exc:
        raise ProviderError(f"TradingView local adapter failed: {exc}") from exc


class MarketDataOrchestrator:
    """Provider-specific specialists run independently; failed sources remain visible."""

    def __init__(self, yahoo=None, binance=None, tradingview=None):
        self.agents={
            "yahoo": yahoo if yahoo is not None else YahooQuoteAgent(),
            "binance": binance if binance is not None else BinanceSpotQuoteAgent(),
            "tradingview": tradingview if tradingview is not None else TradingViewQuoteAgent(),
        }

    def get_quote(self, symbol: str, asset_class: str) -> QuoteResult:
        pairs=pairs_for_asset(symbol,asset_class)
        from concurrent.futures import ThreadPoolExecutor
        configured_tv = bool(getattr(self.agents["tradingview"],"adapter_url",None))
        order=[name for name in ("binance","yahoo","tradingview") if name in pairs and
               (name!="tradingview" or configured_tv)]
        if not order:
            raise ProviderError("No market quote providers configured for instrument.")
        # Parallel reads; each adapter stays isolated and cannot access exchange accounts.
        def fetch(name: str):
            try:
                result=self.agents[name].fetch(pairs[name])
                return ProviderAttempt(provider=name,status="ok",symbol=pairs[name],quote=result)
            except (ProviderError,ValueError,OSError,KeyError) as exc:
                return ProviderAttempt(provider=name,status="failed",symbol=pairs[name],
                                       error=str(exc)[:350])
        with ThreadPoolExecutor(max_workers=len(order)) as pool:
            attempts=list(pool.map(fetch,order))
        good=[a.quote for a in attempts if a.quote]
        # Do not average USD and USDT or mix separate exchanges.
        priority=("binance","yahoo","tradingview") if asset_class=="crypto" else ("yahoo","tradingview")
        selected=next((q for p in priority for q in good if q.provider==p),None)
        return QuoteResult(requested_symbol=symbol,asset_class=asset_class,
                           selected=selected,attempts=attempts)


def quote_answer(result: QuoteResult) -> str:
    selected=result.selected
    if selected is None:
        lines=[f"Não foi possível obter uma cotação confirmada para {result.requested_symbol}."]
        lines += [f"{a.provider}: {a.error}" for a in result.attempts if a.error]
        return "\n".join(lines)
    name=selected.instrument if selected.instrument else selected.symbol
    value=f"{selected.price:,.4f}".replace(","," ").replace(".",",")
    stamp=selected.at.strftime("%d/%m/%Y %H:%M UTC")
    lines=[f"Última cotação publicada de {name} ({selected.symbol}): {value} {selected.currency}.",
           f"Referência temporal: {stamp} ({selected.timestamp_kind.replace('_',' ')}).",
           f"Fonte: {selected.provider.upper()} · {selected.venue}.",
           "A disponibilidade em tempo real não está confirmada; a cotação pode estar diferida."]
    alternatives=[a.quote for a in result.attempts if a.quote and a.quote.provider != selected.provider]
    if alternatives:
        parts=[f"{q.provider.upper()} {q.price:g} {q.currency}" for q in alternatives]
        lines.append("Outras fontes: "+", ".join(parts)+".")
    return "\n".join(lines)
