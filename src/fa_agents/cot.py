"""CFTC Commitments of Traders: read-only source adapters and normalized specialist.

The report families are not interchangeable. A COT record describes a futures
contract market, never the underlying single stock. CFTC reporting is weekly
and its Tuesday observation date is NOT the Friday publication date.
"""
from __future__ import annotations

import json
import os
import re
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Protocol
from urllib.parse import urlencode

from .models import AgentResult, Evidence, ResearchRequest, CotData, CotWeek, CotPosition, CotMarket
from .providers import ProviderError, fetch_bytes, now

DATASETS = {
    "tff": "gpe5-46if",
    "disaggregated": "72hh-3qpy",
    "legacy": "6dca-aqww",
}
# All versions currently use futures-only to prevent combining incompatible data.
GROUP_FIELDS = {
    "tff": {
        "Dealers": (("dealer_positions_long_all",), ("dealer_positions_short_all",)),
        "Asset Managers": (("asset_mgr_positions_long", "asset_mgr_positions_long_all"),
                           ("asset_mgr_positions_short", "asset_mgr_positions_short_all")),
        "Leveraged Money": (("lev_money_positions_long", "lev_money_positions_long_all"),
                            ("lev_money_positions_short", "lev_money_positions_short_all")),
        "Other Reportables": (("other_rept_positions_long", "other_rept_positions_long_all"),
                              ("other_rept_positions_short", "other_rept_positions_short_all")),
        "Non-Reportables": (("nonrept_positions_long_all",), ("nonrept_positions_short_all",)),
    },
    "disaggregated": {
        "Producers/Merchants": (("prod_merc_positions_long",), ("prod_merc_positions_short",)),
        "Swap Dealers": (("swap_positions_long_all",), ("swap__positions_short_all","swap_positions_short_all")),
        "Managed Money": (("m_money_positions_long_all",), ("m_money_positions_short_all",)),
        "Other Reportables": (("other_rept_positions_long",), ("other_rept_positions_short",)),
        "Non-Reportables": (("nonrept_positions_long_all",), ("nonrept_positions_short_all",)),
    },
    "legacy": {
        "Commercial": (("comm_positions_long_all",), ("comm_positions_short_all",)),
        "Non-Commercial": (("noncomm_positions_long_all",), ("noncomm_positions_short_all",)),
        "Non-Reportables": (("nonrept_positions_long_all",), ("nonrept_positions_short_all",)),
    },
}

CONTRACT_PATTERN = re.compile(r"^[0-9A-Za-z]{4,12}$")
ALIASES = {
    "bitcoin":("tff","BITCOIN"),"btc":("tff","BITCOIN"),
    "ethereum":("tff","ETHER"),"ether":("tff","ETHER"),"eth":("tff","ETHER"),
    "ouro": ("disaggregated","GOLD"),"gold":("disaggregated","GOLD"),
    "prata": ("disaggregated","SILVER"),"silver":("disaggregated","SILVER"),
    "petroleo":("disaggregated","CRUDE OIL"),"wti":("disaggregated","CRUDE OIL"),
    "crude":("disaggregated","CRUDE OIL"),
    "natural gas":("disaggregated","NATURAL GAS"),"gas natural":("disaggregated","NATURAL GAS"),
    "cobre":("disaggregated","COPPER"),"copper":("disaggregated","COPPER"),
    "nasdaq 100":("tff","NASDAQ-100"),"nasdaq":("tff","NASDAQ-100"),
    "s&p 500":("tff","S&P 500"),"sp500":("tff","S&P 500"),
    "euro":("tff","EURO FX"),"eur":("tff","EURO FX"),
    "treasury":("tff","TREASURY"),
}
COT_INTENT = re.compile(r"\b(cot|commitments? of traders|posicionamento dos traders)\b", re.I)


def normalize(value: str) -> str:
    normalized = unicodedata.normalize("NFKD",value.casefold())
    return "".join(char for char in normalized if not unicodedata.combining(char))


def is_cot_question(question: str) -> bool:
    return bool(COT_INTENT.search(normalize(question)))


def select_cot_market(question: str, symbol: str, report_type: str | None = None) -> tuple[str,str|None]:
    """Return report family + *search phrase*, NOT an unverified contract code."""
    text=normalize(question)
    for term,(family,needle) in sorted(ALIASES.items(),key=lambda pair:-len(pair[0])):
        if re.search(r"(?<![a-z0-9])" + re.escape(term) + r"(?![a-z0-9])", text):
            return report_type or family,needle
    # If the user asks simply for COT with BTC/ETH selected, resolve the
    # selected underlying to a futures-market *search*, never a silent contract.
    if re.fullmatch(r"(qual e o\s+)?cot(?:\s+(?:do ativo|deste ativo))?\s*[?!.]*",text.strip()):
        asset=symbol.upper().strip().removesuffix("USDT").removesuffix("-USD")
        if asset in {"BTC","ETH"}:
            return report_type or "tff", {"BTC":"BITCOIN","ETH":"ETHER"}[asset]
    # A ticker for an individual equity is not a supported COT market mapping.
    return report_type or "tff",None


def _num(row: dict, names: tuple[str,...]) -> int | None:
    for key in names:
        if key not in row or row[key] is None or row[key]=="":
            continue
        try:
            value=float(row[key])
            if not value.is_integer() or value<0:
                return None
            return int(value)
        except (TypeError,ValueError,OverflowError):
            return None
    return None


def _date(value) -> date:
    try:
        day=date.fromisoformat(str(value)[:10])
    except (TypeError,ValueError) as exc:
        raise ProviderError("CFTC record has an invalid report date.") from exc
    if day>now().date():
        raise ProviderError("CFTC record has a future report date.")
    return day


class CotSource(Protocol):
    def search(self, report_type: str, term: str) -> list[dict]: ...
    def history(self, report_type: str, market_code: str, limit: int) -> list[dict]: ...


class CftcApiSource:
    """CFTC Public Reporting Socrata official resources; no API key required."""

    source="cftc"

    def __init__(self, loader=None):
        self.loader=loader

    def _fetch(self, report_type: str, params: dict) -> list[dict]:
        if report_type not in DATASETS:
            raise ProviderError("COT report family not supported.")
        url=("https://publicreporting.cftc.gov/resource/"+DATASETS[report_type]+
             ".json?"+urlencode(params))
        raw=self.loader(url) if self.loader else fetch_bytes(url,"FA-Agent/0.6 CFTC Public Data Research")
        try:
            result=json.loads(raw)
        except (ValueError,UnicodeDecodeError,TypeError) as exc:
            raise ProviderError("Invalid CFTC JSON response.") from exc
        if not isinstance(result,list):
            raise ProviderError("CFTC returned a query error instead of a dataset.")
        if len(result)>150:
            raise ProviderError("CFTC response exceeds supported page length.")
        return result

    def search(self, report_type:str, term:str) -> list[dict]:
        phrase=term.strip().upper()
        if len(phrase)<2 or len(phrase)>60 or not re.fullmatch(r"[A-Z0-9 &/.'-]+",phrase):
            raise ProviderError("COT contract search term invalid.")
        safe=phrase.replace("'","''")
        # Group at the contract-code grain to avoid duplicate weekly rows.
        return self._fetch(report_type,{
            "$select":"cftc_contract_market_code,contract_market_name,market_and_exchange_names",
            "$where":f"upper(market_and_exchange_names) like '%{safe}%'",
            "$group":"cftc_contract_market_code,contract_market_name,market_and_exchange_names",
            "$order":"contract_market_name ASC",
            "$limit":"25",
        })

    def history(self,report_type:str,market_code:str,limit:int=52) -> list[dict]:
        if not CONTRACT_PATTERN.fullmatch(market_code):
            raise ProviderError("CFTC market code invalid.")
        if limit<2 or limit>150:
            raise ProviderError("History limit outside allowed range.")
        return self._fetch(report_type,{
            "$where":f"cftc_contract_market_code='{market_code}'",
            "$order":"report_date_as_yyyy_mm_dd DESC",
            "$limit":str(limit),
        })


class PostgresCotSource:
    """Future replacement source, same contract as CftcApiSource.

    Requires a separately provisioned local/read-only PostgreSQL DB.
    Keeps backend independent from SysTrd and its schema.
    """

    source="postgres"

    def __init__(self,dsn: str):
        if not dsn:
            raise ProviderError("FA_COT_PG_DSN not configured.")
        self.dsn=dsn

    def _connect(self):
        try:
            import psycopg
        except ImportError as exc:
            raise ProviderError('Install "pip install -e .[cot_pg]" for Postgres COT.') from exc
        return psycopg.connect(self.dsn,connect_timeout=6)

    def search(self,report_type:str,term:str)->list[dict]:
        _validate_type(report_type)
        phrase=term.strip().upper()
        if len(phrase)<2 or len(phrase)>60:
            raise ProviderError("COT contract search term invalid.")
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SET TRANSACTION READ ONLY")
                cur.execute("""
                    SELECT DISTINCT contract_code,contract_name,market_name
                    FROM cot_reports
                    WHERE report_type=%s AND UPPER(market_name) LIKE %s
                    ORDER BY contract_name
                    LIMIT 25
                """,(report_type,"%"+phrase+"%"))
                return [{"cftc_contract_market_code":code,
                         "contract_market_name":name,
                         "market_and_exchange_names":market}
                        for code,name,market in cur.fetchall()]

    def history(self,report_type:str,market_code:str,limit:int=52)->list[dict]:
        _validate_type(report_type)
        if not CONTRACT_PATTERN.fullmatch(market_code) or not 2<=limit<=150:
            raise ProviderError("Invalid COT history query.")
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SET TRANSACTION READ ONLY")
                cur.execute("""
                    SELECT report_date, contract_name, market_name, open_interest,
                           source_fields
                    FROM cot_reports WHERE report_type=%s AND contract_code=%s
                    ORDER BY report_date DESC LIMIT %s
                """,(report_type,market_code,limit))
                data=[]
                for day,contract,market,open_interest,raw in cur.fetchall():
                    item=dict(raw)
                    item.update({
                        "report_date_as_yyyy_mm_dd":day.isoformat(),
                        "contract_market_name":contract,
                        "market_and_exchange_names":market,
                        "cftc_contract_market_code":market_code,
                        "open_interest_all":open_interest,
                    })
                    data.append(item)
                return data


def _validate_type(report_type):
    if report_type not in DATASETS:
        raise ProviderError("Unknown COT family. Use tff, disaggregated or legacy.")


def get_source():
    source=os.getenv("FA_COT_SOURCE","cftc").strip().lower()
    if source=="cftc":
        return CftcApiSource()
    if source=="postgres":
        return PostgresCotSource(os.getenv("FA_COT_PG_DSN",""))
    raise ProviderError("FA_COT_SOURCE must be cftc or postgres.")


def _market_candidates(rows:list[dict]) -> list[CotMarket]:
    seen={}
    for record in rows:
        code=str(record.get("cftc_contract_market_code") or "")
        if not CONTRACT_PATTERN.fullmatch(code):
            continue
        if code not in seen:
            seen[code]=CotMarket(code=code,
                name=str(record.get("contract_market_name") or code),
                market=str(record.get("market_and_exchange_names") or "Unknown venue"))
    return list(seen.values())


def compute_cot(report_type:str,code:str,history:list[dict],source_name="cftc") -> CotData:
    _validate_type(report_type)
    if not CONTRACT_PATTERN.fullmatch(code):
        raise ProviderError("Invalid CFTC contract market code.")
    records={}
    for record in history:
        if str(record.get("cftc_contract_market_code"))!=code:
            raise ProviderError("Source returned a different contract market code.")
        dt=_date(record.get("report_date_as_yyyy_mm_dd"))
        interest=_num(record,("open_interest_all",))
        if interest is None or interest<=0:
            continue
        groups=[]
        for name,(long_keys,short_keys) in GROUP_FIELDS[report_type].items():
            long=_num(record,long_keys)
            short=_num(record,short_keys)
            if long is None or short is None:
                continue
            groups.append(CotPosition(group=name,long=long,short=short,
                net=long-short,net_pct_oi=round(100*(long-short)/interest,3)))
        if not groups:
            continue
        entry=CotWeek(
            report_date=dt,open_interest=interest,groups=groups,
        )
        if dt in records:
            raise ProviderError("Duplicate COT report date returned for contract code.")
        records[dt]=entry
    weeks=[records[dt] for dt in sorted(records)]
    if not weeks:
        raise ProviderError("CFTC did not return complete numerical position records.")
    latest=weeks[-1]
    if len(weeks)>1:
        previous={p.group:p for p in weeks[-2].groups}
        for position in latest.groups:
            if position.group in previous:
                position.net_wow=position.net-previous[position.group].net
    # CFTC Tuesday reporting date is not a precise publication timestamp.
    return CotData(report_type=report_type,market_code=code,
        market_name=str(history[0].get("market_and_exchange_names") or code),
        source=source_name,weeks=weeks,latest=latest,
        source_url=("https://publicreporting.cftc.gov/resource/"+
                    DATASETS[report_type]+".json"),
    )


def cot_specialist(request: ResearchRequest, svc) -> AgentResult:
    """Specialist entry point for the existing LangGraph worker."""
    if svc.demo:
        return AgentResult(agent_id="cot",status="no_data",
                           limitations=["COT demo fixture not available; select Live for official CFTC records."])
    family,needle=select_cot_market(request.question,request.symbol,request.cot_report_type)
    _validate_type(family)
    source=get_source()
    code=request.cot_market_code
    if not code:
        if not needle:
            return AgentResult(agent_id="cot",status="no_data",
                summary="COT reports cover futures contract markets, not individual company shares.",
                limitations=["Select a CFTC contract market. An equity ticker is not an automatic proxy for an index future.",
                             "Try 'COT do ouro', 'COT do petróleo' or search for a futures contract."])
        candidates=_market_candidates(source.search(family,needle))
        if not candidates:
            return AgentResult(agent_id="cot",status="no_data",
                summary=f"No CFTC contract matching {needle!r} in {family} futures-only.",
                limitations=["Verify the CFTC contract name or choose another COT report family."])
        if len(candidates)!=1:
            cot=CotData(report_type=family,source=source.source,markets=candidates)
            return AgentResult(agent_id="cot",status="partial",
                summary=f"Found {len(candidates)} CFTC contracts matching {needle}. Choose an exact contract.",
                cot=cot,limitations=[
                    "A text search does not uniquely identify a CFTC futures contract. Choose a contract code.",
                    "No market positioning claims were made before confirming the contract.",
                ])
        code=candidates[0].code
    rows=source.history(family,code,limit=52)
    if not rows:
        return AgentResult(agent_id="cot",status="no_data",
            summary=f"No CFTC weekly reports for contract code {code}.",
            limitations=["No COT data found from the configured source."])
    data=compute_cot(family,code,rows,source_name=source.source)
    current=data.latest
    assert current is not None
    claims=[]
    metrics:dict[str,str|int|float|None]={
        "contract_code":code,"report_type":family,
        "open_interest_contracts":current.open_interest,
        "report_date":current.report_date.isoformat(),
    }
    for group in current.groups:
        ident=re.sub(r"[^a-z0-9]+","_",group.group.lower()).strip("_")
        metrics[ident+"_net_contracts"]=group.net
        metrics[ident+"_net_pct_oi"]=group.net_pct_oi
        if group.net_wow is not None:
            claims.append(f"{group.group}: net {group.net:+,} contracts, weekly change {group.net_wow:+,}.")
    source_url=data.source_url or "https://publicreporting.cftc.gov/"
    return AgentResult(
        agent_id="cot",status="completed" if current.groups else "no_data",
        summary=f"CFTC {family} futures-only positioning for {data.market_name}; report {current.report_date}.",
        cot=data,metrics=metrics,claims=claims,
        evidence=[Evidence(
            source_id=f"cftc-{family}-{code}-{current.report_date.isoformat()}",
            source_name="CFTC Public Reporting" if source.source=="cftc" else "PostgreSQL COT mirror",
            source_url=source_url,retrieved_at=now(),
            observed_at=datetime.combine(current.report_date,datetime.min.time(),timezone.utc),
            text_excerpt=f"Weekly Tuesday positions for CFTC contract {code}; publication date not supplied.",
        )],
        limitations=[
            "Tuesday positions, normally published on Friday. Report date is NOT publication date; do not use as point-in-time trading data without the actual availability timestamp.",
            "Contracts and report families are not interchangeable; futures-only only.",
            "Positioning is not a causal trading signal or the positioning of an individual listed company.",
            "Weekly net positions and net percentages are descriptive; no statistically validated predictive inference.",
        ],
    )


def cot_answer(result:AgentResult) -> str:
    if result.cot and result.cot.markets:
        items="; ".join(f"{m.name} [{m.code}]" for m in result.cot.markets[:8])
        return f"{result.summary}\nEscolha um contrato na secção COT: {items}."
    if not result.cot or not result.cot.latest:
        return result.summary+"\n"+" ".join(result.limitations[:2])
    cot=result.cot
    latest=cot.latest
    rows="\n".join(f"{p.group}: long {p.long:,}, short {p.short:,}, net {p.net:+,} "
                   f"({p.net_pct_oi:+.2f}% do open interest)."
                   for p in latest.groups)
    return (f"COT {cot.report_type.upper()} · {cot.market_name}\n"
            f"Dados de {latest.report_date}, open interest {latest.open_interest:,} contratos.\n"
            f"{rows}\n"
            "Dados CFTC semanais (terça-feira), publicados normalmente na sexta-feira. "
            "Não são cotações em tempo real nem sinais de negociação.")
