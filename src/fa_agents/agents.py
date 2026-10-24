"""Specialist capabilities; all financial calculations are deterministic."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from .models import AgentResult, Evidence, ResearchRequest
from .providers import SEC, NewsRSS, DemoSEC, DemoNews, ProviderError, annual, prices_from_csv, now, cutoff_at


@dataclass
class Services:
    sec: Any = None
    news: Any = None
    prices_csv: str | None = None
    demo: bool = False

    @classmethod
    def build(cls, mode="live", prices_csv=None) -> "Services":
        if mode == "demo":
            return cls(DemoSEC(), DemoNews(), prices_csv, True)
        if mode != "live":
            raise ValueError(f"Unsupported mode {mode}")
        return cls(None, NewsRSS(), prices_csv, False)

    def sec_reader(self):
        if self.sec is None:
            self.sec = SEC()
        return self.sec


def evidence(identifier, name, url, *, published=None, observed=None, demo=False, excerpt=None):
    return Evidence(source_id=identifier, source_name=name, source_url=url,
                    retrieved_at=now(), published_at=published,
                    observed_at=observed, is_synthetic=demo, text_excerpt=excerpt)


def financial(request: ResearchRequest, svc: Services) -> AgentResult:
    if request.asset_class.value != "equity":
        return AgentResult(agent_id="fundamental", status="no_data",
                           limitations=["SEC financial data covers US equities only."])
    sec = svc.sec_reader()
    issuer = sec.resolve(request.symbol)
    facts = sec.facts(issuer)
    tags = {
        "revenue": ("RevenueFromContractWithCustomerExcludingAssessedTax", "Revenues", "SalesRevenueNet"),
        "net_income": ("NetIncomeLoss",),
        "operating_cash_flow": ("NetCashProvidedByUsedInOperatingActivities",),
        "capex": ("PaymentsToAcquirePropertyPlantAndEquipment",),
    }
    data = {name: annual(facts, candidates, request.as_of) for name, candidates in tags.items()}
    measures: dict[str, float | str | None] = {"company": issuer.name}
    sources: list[Evidence] = []
    claims: list[str] = []
    for metric, rows in data.items():
        if not rows:
            continue
        current = rows[0]
        measures[metric + "_usd"] = current["value"]
        measures[metric + "_period"] = current["end"]
        src = ("https://example.com/synthetic-sec-facts" if svc.demo else
               f"https://data.sec.gov/api/xbrl/companyfacts/CIK{issuer.cik10}.json")
        sources.append(evidence(
            metric + "-" + current["end"], "SYNTHETIC SEC FIXTURE" if svc.demo else "SEC XBRL",
            src, published=datetime.fromisoformat(current["filed"]).replace(tzinfo=timezone.utc),
            observed=datetime.fromisoformat(current["end"]).replace(tzinfo=timezone.utc),
            demo=svc.demo, excerpt=f"{metric}: {current['value']:,.0f} USD at {current['end']}"
        ))
    rev = data["revenue"]
    ni = data["net_income"]
    cf, capex = data["operating_cash_flow"], data["capex"]
    if len(rev) > 1 and rev[1]["value"]:
        growth = 100 * (rev[0]["value"] / rev[1]["value"] - 1)
        measures["annual_revenue_growth_pct"] = round(growth, 2)
        claims.append(f"Reported annual revenue growth: {growth:.2f}%.")
    if rev and ni and rev[0]["end"] == ni[0]["end"] and rev[0]["value"]:
        margin = 100 * ni[0]["value"] / rev[0]["value"]
        measures["net_margin_pct"] = round(margin, 2)
        claims.append(f"Reported net margin: {margin:.2f}%.")
    if cf and capex and cf[0]["end"] == capex[0]["end"]:
        fcf = cf[0]["value"] - capex[0]["value"]
        measures["fcf_proxy_usd"] = fcf
        claims.append(f"Operating cash flow less PPE purchases: {fcf:,.0f} USD.")
    return AgentResult(
        agent_id="fundamental", status="completed" if sources else "no_data",
        summary=f"Annual filed SEC financial metrics for {issuer.name}; not an investment valuation."
                if sources else f"No suitable annual SEC facts for {issuer.name}.",
        claims=claims, metrics=measures, evidence=sources,
        limitations=[
            "Annual 10-K values only; amended filings and XBRL tag coverage may vary.",
            "Some extracted metrics can refer to different year-ends. Cross-metric ratios require matching periods.",
            "FCF proxy excludes capital expenditures not reported under the selected PPE tag.",
            "No estimates, share price, valuation or footnote audit.",
        ] + (["SYNTHETIC TEST NUMBERS, NOT REAL COMPANY DATA."] if svc.demo else []),
    )


def filings(request: ResearchRequest, svc: Services) -> AgentResult:
    if request.asset_class.value != "equity":
        return AgentResult(agent_id="filings", status="no_data",
                           limitations=["US SEC issuer filings only."])
    sec = svc.sec_reader()
    issuer = sec.resolve(request.symbol)
    recent = sec.submissions(issuer).get("filings", {}).get("recent", {})
    cutoff = cutoff_at(request.as_of).date().isoformat()
    found: list[Evidence] = []
    for i, form in enumerate(recent.get("form", [])):
        if form not in ("10-K", "10-Q", "8-K"):
            continue
        try:
            day = str(recent["filingDate"][i])
            accession = str(recent["accessionNumber"][i])
            document = str(recent["primaryDocument"][i])
        except (KeyError, IndexError, TypeError):
            continue
        if day > cutoff:
            continue
        url = ("https://example.com/synthetic-filing" if svc.demo else
               f"https://www.sec.gov/Archives/edgar/data/{issuer.cik}/{accession.replace('-', '')}/{document}")
        found.append(evidence(
            "filing-" + accession, form + " metadata from SEC", url, demo=svc.demo,
            published=datetime.fromisoformat(day).replace(tzinfo=timezone.utc),
            excerpt=f"{form} filed {day}. Full text not examined.",
        ))
        if len(found) >= 5:
            break
    return AgentResult(
        agent_id="filings", status="partial" if found else "no_data",
        summary=f"Identified {len(found)} primary filings for {issuer.name}.",
        evidence=found,
        limitations=["Only filing metadata was retrieved; company disclosures have NOT been read or analyzed."]
        + (["SYNTHETIC TEST RECORDS."] if svc.demo else []),
    )


def news(request: ResearchRequest, svc: Services) -> AgentResult:
    articles = svc.news.headlines(request.symbol, as_of=request.as_of)
    sources = [evidence(
        f"news-{i}", item["publisher"], item["url"], published=item.get("date"),
        demo=svc.demo, excerpt=item["title"][:300],
    ) for i, item in enumerate(articles, start=1)]
    return AgentResult(
        agent_id="news", status="partial" if sources else "no_data",
        summary=f"Discovered {len(sources)} headline(s), not full article analyses.",
        evidence=sources,
        limitations=[
            "RSS headline discovery is incomplete, may contain duplicates and is not a validated article body.",
            "Do not infer company performance or sentiment from headlines alone.",
            "Live RSS cannot support historical point-in-time testing.",
        ] + (["SYNTHETIC TEST NEWS."] if svc.demo else []),
    )


def technical(request: ResearchRequest, svc: Services) -> AgentResult:
    if not svc.prices_csv:
        return AgentResult(agent_id="technical", status="no_data",
                           limitations=["Supply --prices CSV with date,close columns."])
    series = prices_from_csv(svc.prices_csv, request.as_of)
    if not series:
        return AgentResult(agent_id="technical", status="no_data",
                           limitations=["No observations at requested date."])
    last = series[-1]
    values = [v for _, v in series]
    metrics: dict[str, float | str | None] = {
        "last_close": last[1], "last_date": last[0], "observations": len(values)
    }
    claims = []
    for window in (20, 50, 200):
        if len(values) >= window:
            avg = sum(values[-window:]) / window
            metrics[f"sma{window}"] = round(avg, 6)
            direction = "above" if last[1] > avg else "below" if last[1] < avg else "equal to"
            claims.append(f"Latest close {direction} SMA{window}.")
    if len(values) >= 2:
        metrics["last_return_pct"] = round((values[-1] / values[-2] - 1) * 100, 4)
    return AgentResult(
        agent_id="technical", status="partial",
        summary="Deterministic daily price analysis from a supplied CSV.",
        claims=claims, metrics=metrics,
        evidence=[evidence("local-prices", "Local CSV - unverified", "https://example.com/local-file",
                           observed=datetime.fromisoformat(last[0]).replace(tzinfo=timezone.utc),
                           demo=svc.demo, excerpt=f"{len(values)} observations; latest {last[0]}")],
        limitations=[
            "No verification of provenance, adjustment for splits/dividends, exchange or currency.",
            "SMAs computed on trading observations, not calendar days. No backtest or trade signals.",
        ],
    )


def review(results: list[AgentResult], selected: list[str]) -> AgentResult:
    """Simple challenge/coverage checks. NOT yet an independent adversarial researcher."""
    gaps = [f"{x.agent_id}: {x.status}" for x in results if x.status != "completed"]
    fundamentals = next((x for x in results if x.agent_id == "fundamental"), None)
    if fundamentals:
        growth = fundamentals.metrics.get("annual_revenue_growth_pct")
        if isinstance(growth, (int, float)) and growth < 0:
            gaps.append("Reported annual revenue contracted. Investigate causes.")
        fcf = fundamentals.metrics.get("fcf_proxy_usd")
        if isinstance(fcf, (int, float)) and fcf < 0:
            gaps.append("FCF proxy is negative. Investigate liquidity and capex.")
    if "valuation" not in selected:
        gaps.append("No independent valuation analysis was performed.")
    return AgentResult(
        agent_id="risk", status="partial",
        summary="Rules-based coverage review; independent risk investigation not implemented.",
        claims=gaps,
        limitations=["Not a complete bear-case or probabilistic risk assessment."],
    )


def run_specialist(name: str, request: ResearchRequest, svc: Services) -> AgentResult:
    implemented = {"fundamental": financial, "filings": filings, "news": news, "technical": technical}
    if name not in implemented:
        return AgentResult(
            agent_id=name, status="not_implemented",
            limitations=["Agent present in catalogue; no live research implementation yet."],
        )
    try:
        return implemented[name](request, svc)
    except (ProviderError, OSError, ValueError, KeyError, TypeError) as exc:
        return AgentResult(
            agent_id=name, status="failed",
            summary=f"Could not complete {name} research.",
            limitations=[f"{type(exc).__name__}: {exc}"],
        )
