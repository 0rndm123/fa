# FA_Agent | Agent and subagent functional registry (v0.6)

Catalogue entries distinguish operational calculation, partial source discovery and planned capabilities.

| ID | Crew | Mission | Status |
| --- | --- | --- | --- |
| financial_data | Financial | Dated annual SEC financial statement history | Working US SEC |
| financial_performance | Financial | Growth, margins, earnings, operating cash, FCF proxy | Working US SEC |
| debt_liquidity | Financial | Debt components, working capital, current ratio | Partial. Depends on accounting tags |
| fundamental | Financial | Basic annual company ratios | Working US SEC |
| filings | Financial | SEC 10-K/10-Q/8-K discovery | Partial. Metadata only |
| governance | Financial | Locate DEF 14A/10-K governance sources | Partial. No board/compensation judgement |
| industry_context | Sector | SEC SIC, limited 10-K industry evidence | Partial. Not market research |
| competition | Sector | Locate 10-K competition evidence | Partial. No verified competitor rankings |
| valuation | Financial | Relative and DCF valuations | Planned |
| industry | Sector | Full peer/industry model | Planned |
| macro | Macro | Monetary policy, macro regimes | Planned |
| news | Events | Current RSS headline metadata | Partial. Headlines only |
| technical | Technical | Daily CSV or vendor hourly price SMA and simple RSI | Partial |
| sentiment | Market | Positioning and flow analysis | Planned |
| crypto_onchain | Crypto | Supply, distribution and protocol metrics | Planned |
| etf | ETF | Holdings and tracking | Planned |
| backtest | Quant | Strategy verification | Planned |
| risk | Risk | Rule-based research coverage review | Partial |

| cot | CFTC Positioning | Weekly futures-only COT analysis by trader category | Working via public CFTC API; contract selection required when ambiguous |

## Market data subagents (separate from the 19 research registrations)

- Yahoo Finance Quote Agent: unofficial chart API, quote, timestamp, hourly OHLC when returned
- Binance Spot Quote Agent: official public ticker and hourly kline endpoints, read-only
- TradingView Quote Agent: local authorized adapter interface only, no public unofficial scraping
- Market Data Orchestrator: determine providers, query independently, compare source times/currencies and expose failures

## Orchestration

- The API automatically maps natural-language financial/debt/governance/competition/sector/technical questions to the corresponding specialist functions.
- Explicit selected agents take precedence.
- LangGraph fans out the workers and joins source-based reports.
- Debt/Performance calculations are deterministic. LLM commentary uses source records when enabled but is **not** an independent SEC extraction tool.
- Web research is read-only. No broker, exchange-account or order functionality.
- Official company filing metadata or raw excerpts do not automatically constitute an evaluated governance or competitive outlook.

## Roadmap: deeper specialists

- Corporate governance: board composition, executive remuneration, voting, insider transactions with verifiable passages
- Peers/sector: verified company universe, share/market sizing, value chain, competitive performance
- Financial: cash flow quality, debt maturities and covenants, profitability decomposition, forecasts and valuation
- Technical: daily/weekly OHLCV, swing structure, indicators with documented calculation variants and backtest links
- Cross-asset: independent challenger, event risk and scenario assessment
