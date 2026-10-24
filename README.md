# FA_Agent | Financial Analysis Research System

Standalone Python **LangGraph / LangChain** financial research application. Repository: 0rndm123/fa.
No dependency on SysTrd, its database or any other application. Future integrations use read-only adapters.

## What actually works (v0.2)

- LangGraph orchestrator: deterministic asset-aware selection, parallel specialist workers, source-gap review, report synthesis.
- **Fundamental**: reads **annual 10-K XBRL** from the US SEC and calculates revenue growth, net margin and a free-cash-flow proxy. These metrics are *not* valuation or investment advice.
- **Filings**: locates up to five filing documents, providing dated original links. Does *not* yet read their content.
- **News**: Google News RSS headline discovery. Does *not* verify or read full articles.
- **Technical**: calculates latest close, SMA20, SMA50, SMA200 where possible from user-provided daily CSV. No signal/backtest yet.
- **Risk**: preliminary rule-based coverage review; independent critical research is not implemented.
- 12 specialist names in catalog. Unimplemented ones explicitly return not_implemented.
- Optional LangChain/OpenAI commentary on evidence already collected, **never** a substitute for evidence.

## Install (Windows PowerShell)

Commands assume Python 3.11+ and Git:

~~~powershell
git clone git@github-rndm123:0rndm123/fa.git
cd fa
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
python -m pytest -q
~~~

If the SSH alias github-rndm123 is not configured, use HTTPS:

~~~powershell
git clone https://github.com/0rndm123/fa.git
~~~

## Test NOW, without any API keys

~~~powershell
fa-agent plan --symbol AAPL --asset-class equity
fa-agent demo --output reports/demo.json
~~~

**DEMO is synthetic**. It intentionally invents figures and news for testing and labels all synthetic records. Never interpret this fixture as real research.

## Real SEC financial analysis

Create an identifying SEC user agent with a real contact email; see SEC fair access conditions.

~~~powershell
$env:SEC_USER_AGENT = "FA_Agent Nelson Contact real.email@domain.com"
fa-agent run --symbol AAPL --asset-class equity --include-agent fundamental --include-agent filings --output reports/aapl.json
~~~

Replace the placeholder with your real email. This is a local environment variable and is not sent to GitHub.

To discover current news headlines (this alone needs no SEC configuration):

~~~powershell
fa-agent run --symbol NVDA --asset-class equity --include-agent news
~~~

To perform price-based analysis, prepare a CSV with header date,close and daily observations in ISO yyyy-mm-dd order (unsorted dates accepted; duplicate dates rejected). Example:

~~~csv
date,close
2026-10-20,100.0
2026-10-21,101.5
~~~

~~~powershell
fa-agent run --symbol AAPL --asset-class equity --include-agent technical --prices C:\path\prices.csv
~~~

To add optional AI-based *commentary* to a live report:

~~~powershell
python -m pip install -e ".[ai]"
# Reads OPENAI_API_KEY_Demo automatically if OPENAI_API_KEY is not defined.
# Do not display or paste the secret key.
fa-agent run --symbol NVDA --asset-class equity --include-agent news --llm --output reports/nvda_ai.json
~~~

The application prefers OPENAI_API_KEY and falls back to OPENAI_API_KEY_Demo, if present in the current Python process environment. This lets an existing Windows environment variable work without copying or printing the secret. Restart the terminal if the variable was configured after opening the session.

Never commit credentials, private financial data, or reports with proprietary content. This GitHub repo is PUBLIC. Model API usage may incur costs.

## Architecture

Request → Plan → Parallel Specialists → Validate → Risk Review → Synthesize → JSON Report.

The orchestrator and sources are separate. Services can be injected for testing and future read-only integrations. See docs/architecture.md, docs/agent_catalog.md and docs/roadmap.md.

## Current limitations

1. SEC coverage is for US equities. Financial metrics may be incomplete and should be checked against audited disclosures.
2. News RSS is a metadata discovery feed, not primary-source article validation or a historical archive.
3. No autonomous investment conclusion, independent bear-case agent, sector research or valuation model yet.
4. No automatic market-price provider or SysTrd integration yet.
5. If external research fails, the run reports errors/partial coverage instead of silently inventing findings.
6. Historical SEC facts filter records on filing date, but present-day ticker mappings are not a complete historically valid security-master.

**No order execution or access to trading accounts.**


## Local research workbench (v0.3)

From the existing clone (e.g. C:\Users\nmota\fa):

~~~powershell
git pull origin main
python -m pip install -e ".[dev,web,ai]"
.\START_FA.bat
~~~

Open http://127.0.0.1:8300 . The UI has a resizable/minimizable/maximizable chat and a separate, tabbed research results workspace. Available tabs adapt to each report: Overview, Financials with history charts and tables, Technical, Sources, Specialists and JSON.

The new **Financial Data** specialist pulls up to six years per available annual XBRL metric from SEC, as original dated observations; the Fundamental specialist performs deterministic calculations separately.

The UI is **local only**, not a production service. Use synthetic DEMO without keys; switch to Live with a real equity ticker for SEC data when SEC_USER_AGENT is set. OPENAI_API_KEY_Demo is recognized for the optional AI commentary. Chat follow-ups provide bounded recent history to the LLM, but live research is re-run for each message; it is not yet a fully autonomous conversational research planner.

Price analysis requires uploading a CSV with date and close columns. The CSV remains temporarily on the local server. Reports are downloadable via Export JSON. See docs/interface.md.


## Market Data Crew — ask for a price (v0.4)

The chat can answer "Qual é o preço da NVIDIA?" by automatically resolving NVIDIA -> NVDA, querying Yahoo Finance (unofficial quote endpoint), and displaying price, currency, source and timestamp. The workbench opens a contextual **Quote** tab, with provider results and a recent chart when available.

For crypto ("Qual o preço do Bitcoin?"), the Market Data Orchestrator queries **Binance Spot** via its public official REST API (BTCUSDT) alongside Yahoo Finance (BTC-USD). USD and USDT are never silently averaged.

A specialized TradingView provider adapter is also included but requires an authorized **local read-only** adapter. TradingView's charting datafeed library is not a public quote service. No credentials or private TradingView endpoints are used. See [Market Data Crew documentation](docs/market_data.md).

For real market prices use **Live** mode; Demo intentionally cannot return real quotes. The first online tests depend on each vendor's availability and may fail due to rate limits or network restrictions. The system must show source failures, not invent prices.
