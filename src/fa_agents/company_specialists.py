"""Read-only business research subagents using dated official SEC records.

Explicitly separates numerical fact research, accounting interpretation and
document-discovery. Governance and competition MUST NOT imply validated
management/peer analysis if only document metadata or limited excerpts exist.
"""
from __future__ import annotations

from datetime import datetime, timezone
from html.parser import HTMLParser
from typing import Any

from .models import AgentResult, Evidence, ResearchRequest, FinancialObservation
from .providers import ProviderError, cutoff_at, fetch_bytes, now, annual


FLOW = {
    "revenue": ("RevenueFromContractWithCustomerExcludingAssessedTax", "Revenues", "SalesRevenueNet"),
    "operating_income": ("OperatingIncomeLoss",),
    "net_income": ("NetIncomeLoss",),
    "operating_cash_flow": ("NetCashProvidedByUsedInOperatingActivities",),
    "capital_expenditure": ("PaymentsToAcquirePropertyPlantAndEquipment",),
}
BALANCE = {
    "cash": ("CashAndCashEquivalentsAtCarryingValue", "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents"),
    "total_assets": ("Assets",),
    "current_assets": ("AssetsCurrent",),
    "current_liabilities": ("LiabilitiesCurrent",),
    "total_liabilities": ("Liabilities",),
    "long_term_debt": ("LongTermDebtNoncurrent", "LongTermDebt"),
    "current_debt": ("LongTermDebtCurrent", "LongTermDebtAndCapitalLeaseObligationsCurrent"),
}
# Note LongTermDebt can include current debt, so never add this fallback to
# LongTermDebtCurrent unless taxonomy confirms their accounting definitions.


def _balance_values(facts: dict, tags: tuple[str, ...], as_of, limit: int = 5) -> list[dict]:
    cutoff = cutoff_at(as_of).date().isoformat()
    gaap = facts.get("facts", {}).get("us-gaap", {})
    for tag in tags:
        best: dict[str, dict] = {}
        for row in gaap.get(tag, {}).get("units", {}).get("USD", []):
            end, filed = row.get("end"), row.get("filed")
            if (not end or not filed or end > cutoff or filed > cutoff or
                row.get("form") not in {"10-K","10-K/A"} or row.get("fp") != "FY"):
                continue
            try:
                value = float(row["val"])
            except (ValueError, KeyError, TypeError):
                continue
            if end not in best or filed > best[end]["filed"]:
                best[end] = {"value": value, "end": end, "filed": filed, "tag": tag}
        if best:
            return sorted(best.values(), key=lambda x:x["end"], reverse=True)[:limit]
    return []


def _obs_and_evidence(dataset, issuer, sec, demo, agent):
    obs, evidence = [], []
    src = ("https://example.com/synthetic-sec-facts" if demo else
           f"https://data.sec.gov/api/xbrl/companyfacts/CIK{issuer.cik10}.json")
    for key, records in dataset.items():
        for row in records:
            identifier = f"{agent}-{row['tag']}-{row['end']}"
            obs.append(FinancialObservation(
                metric=key,period_end=row["end"],value=row["value"],
                unit="USD",source_id=identifier,
            ))
            evidence.append(Evidence(
                source_id=identifier,source_name="Synthetic companyfacts" if demo else "SEC companyfacts",
                source_url=src,observed_at=datetime.fromisoformat(row["end"]).replace(tzinfo=timezone.utc),
                published_at=datetime.fromisoformat(row["filed"]).replace(tzinfo=timezone.utc),
                retrieved_at=now(),is_synthetic=demo,
                text_excerpt=f"{key}: {row['value']:.0f} USD; period {row['end']}",
            ))
    return obs, evidence


def performance(request:ResearchRequest,svc) -> AgentResult:
    if request.asset_class.value!="equity":
        return AgentResult(agent_id="financial_performance",status="no_data",
                           limitations=["Only US SEC company facts supported."])
    sec=svc.sec_reader()
    issuer=sec.resolve(request.symbol)
    facts=sec.facts(issuer)
    dataset={k:annual(facts,tags,request.as_of,limit=5) for k,tags in FLOW.items()}
    observations,sources=_obs_and_evidence(dataset,issuer,sec,svc.demo,"performance")
    metrics:dict[str,float|str|None]={"company":issuer.name}
    claims=[]
    for metric, rows in dataset.items():
        if rows:
            metrics[metric+"_usd"]=rows[0]["value"]
            metrics[metric+"_period"]=rows[0]["end"]
            if len(rows)>1 and rows[1]["value"] and metric in {"revenue","operating_income","net_income"}:
                growth=100*(rows[0]["value"]/rows[1]["value"]-1)
                metrics[metric+"_yoy_pct"]=round(growth,2)
                claims.append(f"{metric} annual growth {growth:.2f}% for {rows[0]['end']}.")
    for metric in ("operating_income","net_income"):
        inc,rev=dataset[metric],dataset["revenue"]
        if inc and rev and inc[0]["end"]==rev[0]["end"] and rev[0]["value"]:
            ratio=100*inc[0]["value"]/rev[0]["value"]
            metrics[metric+"_margin_pct"]=round(ratio,2)
            claims.append(f"{metric} margin {ratio:.2f}% for {rev[0]['end']}.")
    ocf,capex=dataset["operating_cash_flow"],dataset["capital_expenditure"]
    if ocf and capex and ocf[0]["end"]==capex[0]["end"]:
        cash=ocf[0]["value"]-capex[0]["value"]
        metrics["fcf_proxy_usd"]=cash
        claims.append(f"Operating cash flow minus PPE spending: {cash:,.0f} USD ({ocf[0]['end']}).")
    return AgentResult(
        agent_id="financial_performance",status="completed" if sources else "no_data",
        summary=f"Examined annual reported performance metrics for {issuer.name}.",
        observations=observations,evidence=sources,metrics=metrics,claims=claims,
        limitations=[
            "Annual SEC 10-K only. Non-GAAP adjustments, estimates and management explanations were not independently audited.",
            "Growth and margins use reported data; ensure accounting comparability between periods.",
            "FCF is a proxy based on operating cash flow less reported PPE purchases.",
        ]+(["Entirely synthetic financial fixture."] if svc.demo else []),
    )


def debt_liquidity(request:ResearchRequest,svc)->AgentResult:
    if request.asset_class.value!="equity":
        return AgentResult(agent_id="debt_liquidity",status="no_data",
                           limitations=["Only US SEC company facts supported."])
    sec=svc.sec_reader();issuer=sec.resolve(request.symbol);facts=sec.facts(issuer)
    dataset={k:_balance_values(facts,tags,request.as_of) for k,tags in BALANCE.items()}
    obs,sources=_obs_and_evidence(dataset,issuer,sec,svc.demo,"debt")
    metrics:dict[str,float|str|None]={"company":issuer.name}
    claims=[]
    for name,rows in dataset.items():
        if rows:
            metrics[name+"_usd"]=rows[0]["value"]
            metrics[name+"_period"]=rows[0]["end"]
    def same(a,b):
        return bool(dataset[a] and dataset[b] and dataset[a][0]["end"]==dataset[b][0]["end"])
    if same("current_assets","current_liabilities") and dataset["current_liabilities"][0]["value"]>0:
        ratio=dataset["current_assets"][0]["value"]/dataset["current_liabilities"][0]["value"]
        metrics["current_ratio"]=round(ratio,3)
        claims.append(f"Current ratio {ratio:.2f} for {dataset['current_assets'][0]['end']}.")
        metrics["working_capital_usd"]=dataset["current_assets"][0]["value"]-dataset["current_liabilities"][0]["value"]
    if same("long_term_debt","cash"):
        # Only noncurrent portion; do not falsely label as total/net debt.
        metrics["noncurrent_debt_less_cash_usd"]=dataset["long_term_debt"][0]["value"]-dataset["cash"][0]["value"]
    if dataset["long_term_debt"] and dataset["current_debt"] and same("long_term_debt","current_debt"):
        if dataset["long_term_debt"][0]["tag"]=="LongTermDebtNoncurrent":
            total=dataset["long_term_debt"][0]["value"]+dataset["current_debt"][0]["value"]
            metrics["reported_debt_components_usd"]=total
            claims.append(f"Sum of separately reported current/noncurrent debt components: {total:,.0f} USD.")
    if not sources:
        return AgentResult(agent_id="debt_liquidity",status="no_data",
                           summary=f"No supported balance-sheet facts for {issuer.name}.",
                           limitations=["Insufficient SEC balance-sheet tags to assess leverage."])
    return AgentResult(
        agent_id="debt_liquidity",status="partial",
        summary=f"Located {len(obs)} balance-sheet observations for {issuer.name}.",
        observations=obs,evidence=sources,metrics=metrics,claims=claims,
        limitations=[
            "SEC balance-sheet snapshot, not a complete debt maturity, interest, lease or covenant review.",
            "Cash may include restricted amounts depending on fallback tag; not always freely available.",
            "LongTermDebt may include current maturities; avoid summing components unless tag explicitly says Noncurrent.",
            "Never conclude solvency or safety solely from these metrics.",
        ]+(["Entirely synthetic financial fixture."] if svc.demo else []),
    )


def _recent_filings(sec, issuer, as_of, form_names:set[str], limit:int=4):
    recent=sec.submissions(issuer).get("filings",{}).get("recent",{})
    cutoff=cutoff_at(as_of).date().isoformat()
    result=[]
    for i,form in enumerate(recent.get("form",[])):
        if form not in form_names:
            continue
        try:
            filed=recent["filingDate"][i]
            if filed>cutoff: continue
            accession=recent["accessionNumber"][i]
            document=recent["primaryDocument"][i]
        except (IndexError,KeyError,TypeError):
            continue
        if not accession or not document:continue
        result.append({
            "form":form, "date":filed,"url":
            f"https://www.sec.gov/Archives/edgar/data/{issuer.cik}/{accession.replace('-','')}/{document}",
            "source_id":f"{form}-{accession}",
        })
        if len(result)>=limit:break
    return result


def governance(request:ResearchRequest,svc)->AgentResult:
    if request.asset_class.value!="equity":
        return AgentResult(agent_id="governance",status="no_data",
                           limitations=["US listed equities only."])
    sec=svc.sec_reader();issuer=sec.resolve(request.symbol)
    filings=_recent_filings(sec,issuer,request.as_of,{"DEF 14A","DEFA14A","10-K"},limit=5)
    evidence=[]
    for filing in filings:
        evidence.append(Evidence(
            source_id=filing["source_id"],source_name="SEC filing index",
            source_url="https://example.com/synthetic-governance" if svc.demo else filing["url"],
            published_at=datetime.fromisoformat(filing["date"]).replace(tzinfo=timezone.utc),
            retrieved_at=now(),is_synthetic=svc.demo,
            text_excerpt=f"{filing['form']} filed {filing['date']}; document text not examined.",
        ))
    return AgentResult(
        agent_id="governance",status="partial" if evidence else "no_data",
        summary=f"Found {len(evidence)} dated corporate governance/proxy filing references for {issuer.name}.",
        evidence=evidence,
        limitations=[
            "Governance data discovery ONLY. Board independence, executive compensation, shareholder rights and insider dealings have not been evaluated.",
            "A DEF 14A proxy statement is a relevant source but its existence is not evidence of good governance.",
            "A full assessment requires document extraction, independent verification and interpretation.",
        ]+(["SYNTHETIC: filing fixtures only."] if svc.demo else []),
    )


class _BodyText(HTMLParser):
    def __init__(self):
        super().__init__();self.parts=[];self.skip=0
    def handle_starttag(self,tag,attrs):
        if tag in {"script","style","noscript"}:self.skip+=1
    def handle_endtag(self,tag):
        if tag in {"script","style","noscript"}:self.skip=max(0,self.skip-1)
    def handle_data(self,data):
        if not self.skip and data.strip():self.parts.append(" ".join(data.split()))


def _section_snippet(sec,issuer,as_of,keyword):
    filings=_recent_filings(sec,issuer,as_of,{"10-K"},limit=1)
    if not filings:return None
    filing=filings[0]
    # Archived SEC documents may be blocked or HTML may contain unstructured text.
    # Always treat any extracted snippet as raw unverified filing text.
    try:
        agent=sec.ua if hasattr(sec,"ua") else ""
        if not agent or "@" not in agent:return None
        body=fetch_bytes(filing["url"],agent)
        if len(body)>4_900_000:return None
        parser=_BodyText();parser.feed(body.decode("utf-8",errors="replace"))
        text=" ".join(parser.parts)
        import re
        matches=list(re.finditer(r"\b"+re.escape(keyword)+r"\b",text,flags=re.IGNORECASE))
        for m in matches:
            # prefer descriptive prose to a heading or table of contents listing
            fragment=text[max(0,m.start()-120):m.start()+850]
            if len(fragment)>260 and len(fragment.split())>45:
                return filing,fragment
    except (ProviderError,ValueError,UnicodeError,OSError):
        return None
    return None


def industry_context(request:ResearchRequest,svc)->AgentResult:
    if request.asset_class.value!="equity":
        return AgentResult(agent_id="industry_context",status="no_data",
                           limitations=["Company SEC sector classification currently covers US issuers only."])
    sec=svc.sec_reader();issuer=sec.resolve(request.symbol);metadata=sec.submissions(issuer)
    sic=metadata.get("sic")
    description=metadata.get("sicDescription")
    source=("https://example.com/synthetic-sec-submissions" if svc.demo else
            f"https://data.sec.gov/submissions/CIK{issuer.cik10}.json")
    evidence=[]
    if sic or description:
        evidence.append(Evidence(
            source_id="sec-sic-"+issuer.cik10,source_name="SEC issuer classification",
            source_url=source,retrieved_at=now(),is_synthetic=svc.demo,
            text_excerpt=f"SIC {sic or 'not supplied'}; description {description or 'not supplied'}.",
        ))
    claims=[f"SEC SIC classification: {sic} ({description})."] if sic and description else []
    found=_section_snippet(sec,issuer,request.as_of,"industry") if not svc.demo else None
    if found:
        filing,snippet=found
        evidence.append(Evidence(
            source_id="industry-10k-"+issuer.cik10,source_name="SEC 10-K extracted raw text",
            source_url=filing["url"],retrieved_at=now(),
            published_at=datetime.fromisoformat(filing["date"]).replace(tzinfo=timezone.utc),
            text_excerpt=snippet,
        ))
    return AgentResult(
        agent_id="industry_context",status="partial" if evidence else "no_data",
        summary=f"Retrieved industry classification and {1 if found else 0} filing text excerpt(s) for {issuer.name}.",
        metrics={"sic":str(sic) if sic is not None else None,"sector_description":description},
        claims=claims,evidence=evidence,
        limitations=[
            "SEC SIC is an issuer classification, not a validated full market/sector study.",
            "Full market size, sector economics, trends, regulation and forecast scenarios not yet independently sourced.",
            "Extracted filing excerpts are raw text, not verified sector facts.",
        ]+(["SYNTHETIC TEST METADATA."] if svc.demo else []),
    )


def competition(request:ResearchRequest,svc)->AgentResult:
    if request.asset_class.value!="equity":
        return AgentResult(agent_id="competition",status="no_data",
                           limitations=["Only issuer 10-K filings currently supported."])
    sec=svc.sec_reader();issuer=sec.resolve(request.symbol)
    found=_section_snippet(sec,issuer,request.as_of,"competition") if not svc.demo else None
    sources=[]
    claims=[]
    if found:
        filing,excerpt=found
        sources.append(Evidence(
            source_id="competition-10k-"+issuer.cik10,
            source_name="SEC 10-K raw excerpt",source_url=filing["url"],
            published_at=datetime.fromisoformat(filing["date"]).replace(tzinfo=timezone.utc),
            retrieved_at=now(),text_excerpt=excerpt,
        ))
        claims.append("A relevant passage was located in the company's 10-K; verify the original source.")
    else:
        filings=_recent_filings(sec,issuer,request.as_of,{"10-K"},limit=1)
        for f in filings:
            sources.append(Evidence(
                source_id="competition-filing-"+issuer.cik10,
                source_name="SEC 10-K filing reference",source_url="https://example.com/demo-10k" if svc.demo else f["url"],
                published_at=datetime.fromisoformat(f["date"]).replace(tzinfo=timezone.utc),
                retrieved_at=now(),is_synthetic=svc.demo,
                text_excerpt="Company 10-K identified; competition section not extracted.",
            ))
    return AgentResult(
        agent_id="competition",status="partial" if sources else "no_data",
        summary=f"Retrieved {len(sources)} relevant filing source(s) for {issuer.name}.",
        claims=claims,evidence=sources,
        limitations=[
            "Not a competitor ranking or peer comparison. No validated competitor universe, market share or comparative financials yet.",
            "A firm's self-description in a 10-K is not independent competitive intelligence.",
            "Research must be triangulated using peer filings and sector datasets before making comparative assertions.",
        ]+(["SYNTHETIC TEST RECORDS."] if svc.demo else []),
    )


SPECIALIST_HANDLERS={
    "financial_performance":performance,
    "debt_liquidity":debt_liquidity,
    "governance":governance,
    "industry_context":industry_context,
    "competition":competition,
}
