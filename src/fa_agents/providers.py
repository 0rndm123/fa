"""Independent read-only data adapters. Live SEC requests require SEC_USER_AGENT."""
from __future__ import annotations

import csv
import json
import os
import threading
from dataclasses import dataclass
from datetime import datetime, timezone, date
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen
from urllib.parse import quote_plus
from urllib.error import URLError
from email.utils import parsedate_to_datetime
import xml.etree.ElementTree as ET


class ProviderError(Exception):
    pass


def now() -> datetime:
    return datetime.now(timezone.utc)


def cutoff_at(as_of: datetime | None) -> datetime:
    dt = as_of or now()
    dt = dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)
    if dt > now():
        raise ProviderError("as_of cannot be in the future.")
    return dt


def fetch_bytes(url: str, user_agent: str) -> bytes:
    if not url.startswith("https://"):
        raise ProviderError("Only HTTPS sources are permitted.")
    req = Request(url, headers={"User-Agent": user_agent})
    try:
        with urlopen(req, timeout=18) as handle:
            return handle.read(5_000_000)
    except (OSError, URLError, TimeoutError) as exc:
        raise ProviderError(f"Unable to read {url}: {exc}") from exc


@dataclass(frozen=True)
class Issuer:
    ticker: str
    cik: int
    name: str

    @property
    def cik10(self) -> str:
        return f"{self.cik:010d}"


class SEC:
    """Public SEC XBRL and submissions, cached for the duration of a run."""

    def __init__(self, user_agent: str | None = None, loader=None):
        self.ua = user_agent or os.getenv("SEC_USER_AGENT", "")
        self.loader = loader
        if self.loader is None and ("@" not in self.ua or len(self.ua) < 8):
            raise ProviderError("Set SEC_USER_AGENT to a name and REAL contact email.")
        self._cache: dict[str, Any] = {}
        self._lock = threading.RLock()

    def get(self, url: str) -> dict:
        with self._lock:
            if url not in self._cache:
                raw = self.loader(url) if self.loader else fetch_bytes(url, self.ua)
                self._cache[url] = json.loads(raw)
            return self._cache[url]

    def resolve(self, symbol: str) -> Issuer:
        matches = [v for v in self.get("https://www.sec.gov/files/company_tickers.json").values()
                   if isinstance(v, dict) and v.get("ticker", "").upper() == symbol.upper()]
        if len(matches) != 1:
            raise ProviderError(f"SEC ticker lookup returned {len(matches)} matches for {symbol}.")
        item = matches[0]
        return Issuer(symbol.upper(), int(item["cik_str"]), item["title"])

    def facts(self, issuer: Issuer) -> dict:
        return self.get(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{issuer.cik10}.json")

    def submissions(self, issuer: Issuer) -> dict:
        return self.get(f"https://data.sec.gov/submissions/CIK{issuer.cik10}.json")


class NewsRSS:
    """Metadata discovery only: headlines do not establish article claims."""

    def headlines(self, symbol: str, *, as_of: datetime | None = None, limit: int = 5) -> list[dict]:
        cutoff = cutoff_at(as_of)
        if as_of and (now() - cutoff).days > 1:
            raise ProviderError("Live RSS is not a historical news archive.")
        query = quote_plus(f'"{symbol}" stock earnings company')
        url = f"https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"
        try:
            root = ET.fromstring(fetch_bytes(url, "FA-Agent/0.2 public research"))
        except ET.ParseError as exc:
            raise ProviderError("Invalid RSS returned by provider.") from exc
        out = []
        for item in root.findall("./channel/item"):
            title = item.findtext("title")
            link = item.findtext("link")
            if not title or not link or not link.startswith("https://"):
                continue
            pub = item.findtext("pubDate")
            try:
                dt = parsedate_to_datetime(pub).astimezone(timezone.utc) if pub else None
            except (ValueError, TypeError):
                dt = None
            if dt and dt > cutoff:
                continue
            src = item.find("source")
            out.append({"title": title, "url": link, "date": dt,
                        "publisher": src.text if src is not None else "RSS"})
            if len(out) >= limit:
                break
        return out


def annual(facts: dict, tags: tuple[str, ...], as_of: datetime | None, limit: int = 2) -> list[dict]:
    """Filed fiscal-year facts, latest revisions known by as_of. Limit defaults to two."""
    cutoff = cutoff_at(as_of).date().isoformat()
    gaap = facts.get("facts", {}).get("us-gaap", {})
    for tag in tags:
        raw = gaap.get(tag, {}).get("units", {}).get("USD", [])
        rows: dict[str, dict] = {}
        for record in raw:
            start, end, filed = record.get("start"), record.get("end"), record.get("filed")
            if not (start and end and filed and filed <= cutoff and end <= cutoff):
                continue
            if record.get("form") not in ("10-K", "10-K/A") or record.get("fp") != "FY":
                continue
            try:
                if not 330 <= (date.fromisoformat(end) - date.fromisoformat(start)).days <= 380:
                    continue
                val = float(record["val"])
            except (KeyError, ValueError, TypeError):
                continue
            if end not in rows or filed > rows[end]["filed"]:
                rows[end] = {"value": val, "end": end, "filed": filed, "tag": tag}
        if rows:
            return sorted(rows.values(), key=lambda x: x["end"], reverse=True)[:limit]
    return []


def prices_from_csv(path: str, as_of: datetime | None = None) -> list[tuple[str, float]]:
    cutoff = cutoff_at(as_of).date().isoformat()
    result: dict[str, float] = {}
    with Path(path).open(encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            fields = {str(k).strip().lower(): v for k, v in row.items()}
            if "date" not in fields or "close" not in fields:
                raise ProviderError("Price CSV must contain date and close columns.")
            day = str(fields["date"])[:10]
            try:
                date.fromisoformat(day)
                close = float(fields["close"])
            except (ValueError, TypeError) as exc:
                raise ProviderError(f"Invalid CSV price row: {row}") from exc
            if close <= 0:
                raise ProviderError("Prices must be positive.")
            if day <= cutoff:
                if day in result:
                    raise ProviderError(f"Duplicate price date: {day}")
                result[day] = close
    return sorted(result.items())


class DemoSEC:
    """Explicitly fabricated offline sample. Does not connect to the SEC."""

    def resolve(self, symbol: str) -> Issuer:
        if symbol.upper() != "DEMO":
            raise ProviderError("Demo mode only accepts DEMO.")
        return Issuer("DEMO", 9999999999, "Synthetic Demo Corporation")

    def facts(self, issuer: Issuer) -> dict:
        tags = {"Revenues": (1000000, 1150000),
                "NetIncomeLoss": (100000, 125000),
                "NetCashProvidedByUsedInOperatingActivities": (140000, 160000),
                "PaymentsToAcquirePropertyPlantAndEquipment": (30000, 40000)}
        def row(y, value):
            return {"start": f"{y}-01-01", "end": f"{y}-12-31",
                    "filed": f"{y+1}-02-10", "form": "10-K", "fp": "FY", "val": value}
        return {"facts": {"us-gaap": {k: {"units": {"USD": [row(2023, a), row(2024, b)]}}
                                        for k, (a, b) in tags.items()}}}

    def submissions(self, issuer: Issuer) -> dict:
        return {"sic": "7372", "sicDescription": "Prepackaged Software (synthetic test classification)",
                "filings": {"recent": {"form": ["10-K", "DEF 14A"],
                    "filingDate": ["2025-02-10", "2025-03-15"],
                    "accessionNumber": ["SYNTHETIC", "SYNTHETIC-PROXY"],
                    "primaryDocument": ["demo.htm","demo-proxy.htm"]}}}


class DemoNews:
    def headlines(self, symbol: str, **kwargs) -> list[dict]:
        return [{"title": "SYNTHETIC EXAMPLE — not real news",
                 "url": "https://example.com/demo-not-real-news",
                 "date": None, "publisher": "Synthetic test fixture"}]
