# FA_Agent | Specialist catalogue

An agent's presence in this catalogue does **not** imply it is operational.

| agent_id | Crew | Function | v0.2 status |
| --- | --- | --- | --- |
| filings | Financial | Identify dated issuer SEC filings | Partial: metadata only |
| fundamental | Financial | Annual fundamental ratios and cash generation | Working: SEC XBRL US equities |
| valuation | Financial | DCF, multiples, peer valuation, assumptions | Not implemented |
| industry | Industry | Competition, sector economics, peer rankings | Not implemented |
| macro | Macro & Market | Monetary conditions, business cycle, asset sensitivity | Not implemented |
| news | News & Events | Dated headlines, future catalysts | Partial: current RSS headlines |
| technical | Technical | Daily trend, levels, momentum, structure | Partial: CSV SMA metrics |
| sentiment | Macro & Market | Market positioning, flows, derivatives | Not implemented |
| crypto_onchain | Asset-Specific | Tokenomics, on-chain metrics | Not implemented |
| etf | Asset-Specific | ETF holdings, fees and tracking | Not implemented |
| backtest | Quant | Statistical reproducibility and signal testing | Not implemented |
| risk | Risk & Decision | Challenge, scenarios, coverage, invalidation | Partial: rules only |

Orchestrator is a control-flow component, not an opinion agent. Validation and Synthesis are separate stages.

## Intended subagents

### Financial
Financial Statements, Growth and Margins, Cash Flow Quality, Debt/Liquidity, Earnings Expectations, Valuation, Governance.

### Technical
Trend and Structure, Price Action, Momentum, Volatility, Volume, Relative Strength, Multi-Timeframe Assessment.

### Sector
Industry Structure, Sector Economics, Competitive Intelligence, Peer Benchmark, Sector Cycle, Structural/Regulatory Change.

### Macro
Growth/Inflation, Monetary Policy, Rates/Credit/Liquidity, Cross-Asset, Flows/Positioning.

### Events
Primary Source Verification, Corporate Events, Catalyst Calendar, Sentiment/Narrative.

### Quant
Signal Formalization, Backtesting, Regime Stability, Statistical Robustness, Conditional Outcomes.

### Risk
Fundamental Risk, Market Risk, Independent Challenger, Scenario/Decision Review.

Specialists may start as functions and data tools. Autonomous LLM subagents are justified only where independent research, reasoning or planning demonstrably improves the result. Financial arithmetic remains deterministic.
