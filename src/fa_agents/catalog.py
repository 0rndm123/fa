"""Agent registry and deterministic first-release orchestration policy."""
from __future__ import annotations
from .models import AssetClass, ResearchRequest

SPECIALISTS: dict[str, str] = {
    "filings": "Corporate filings and disclosures",
    "financial_data": "Financial data retrieval and historical observations",
    "financial_performance": "Operating performance, growth, profitability and cash flow",
    "debt_liquidity": "Corporate debt, balance sheet and liquidity",
    "governance": "Management, board and shareholder governance source discovery",
    "industry_context": "Sector classification, sector dynamics and industry filings",
    "competition": "Company rivals and competitive context research",
    "fundamental": "Financial statements, profitability and cash flow",
    "valuation": "Valuation models and sensitivity",
    "industry": "Industry and competitors",
    "macro": "Economic and monetary conditions",
    "news": "News metadata and catalysts",
    "technical": "Price/indicator structure",
    "sentiment": "Positioning and flows",
    "crypto_onchain": "Crypto tokenomics and on-chain",
    "etf": "ETF structure and tracking",
    "backtest": "Quantitative verification",
    "risk": "Review and challenge",
}
_DEFAULT = {
    AssetClass.EQUITY: ("financial_data", "financial_performance", "debt_liquidity", "fundamental", "filings", "news", "technical", "risk"),
    AssetClass.ETF: ("etf", "news", "technical", "risk"),
    AssetClass.CRYPTO: ("crypto_onchain", "news", "technical", "risk"),
    AssetClass.COMMODITY: ("macro", "news", "technical", "risk"),
    AssetClass.FX: ("macro", "news", "technical", "risk"),
    AssetClass.INDEX: ("macro", "news", "technical", "risk"),
    AssetClass.OTHER: ("news", "risk"),
}


def choose_agents(request: ResearchRequest) -> list[str]:
    selected = list(_DEFAULT[request.asset_class]) if request.include_agents is None else request.include_agents
    unknown = (set(selected) | set(request.exclude_agents)) - SPECIALISTS.keys()
    if unknown:
        raise ValueError(f"Unknown agent(s): {', '.join(sorted(unknown))}")
    excluded = set(request.exclude_agents)
    return list(dict.fromkeys(a for a in selected if a not in excluded))


def select_for_question(request: ResearchRequest) -> list[str]:
    """Route natural-language questions to independent specialist capabilities.

    Explicit manual agent selection has priority. Matching rules are conservative
    and do not pretend to constitute a full autonomous AI planner.
    """
    if request.include_agents is not None:
        return choose_agents(request)
    if request.asset_class != AssetClass.EQUITY:
        return choose_agents(request)
    import re
    import unicodedata
    normalized=unicodedata.normalize("NFKD",request.question.casefold())
    normalized="".join(c for c in normalized if not unicodedata.combining(c))
    words=set(re.findall(r"[a-z]+",normalized))
    groups={
        "financial_performance":{
            "financial", "financials","financeiros","financeira","financas",
            "receitas","revenue","lucro","lucros","earnings","profit",
            "margem","margens","margins","rentabilidade","crescimento",
            "cashflow","ebitda","resultados","performance","lucro"},
        "debt_liquidity":{
            "divida","dividas","debt","debts","liquidez","liquidity","leverage",
            "endividamento","solvabilidade","balanco","passivo","covenant"},
        "governance":{
            "governance","governanca","gestao","management","board","administracao",
            "ceo","insiders","remuneracao","executivos","diretores"},
        "competition":{
            "concorrencia","concorrente","concorrentes","competitors",
            "competition","peers","competitivo","rivals"},
        "industry_context":{
            "setor","sector","sectors","industry","mercado","industria",
            "segmento","regulacao","segment","economic"},
        "technical":{
            "technical","tecnica","tecnico","tecnicos","graficos","grafico",
            "chart","trend","tendencia","rsi","ema","sma","suporte",
            "resistencia","momentum","candles","volatilidade","moving","atr"},
    }
    matched={group for group,patterns in groups.items() if words & patterns}
    if not matched:return choose_agents(request)
    result=[]
    if "technical" in matched:result.append("technical")
    if "debt_liquidity" in matched:result.extend(["debt_liquidity","financial_data"])
    if "financial_performance" in matched:
        result.extend(["financial_performance","fundamental","financial_data"])
    if "governance" in matched:result.append("governance")
    if "competition" in matched:result.extend(["competition","industry_context"])
    if "industry_context" in matched:result.append("industry_context")
    if "technical" in matched and "financial_performance" in matched:result.append("risk")
    return list(dict.fromkeys(result))
