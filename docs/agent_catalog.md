# Functional catalogue of specialists

`Orchestrator` is the workflow coordinator, **not** another market opinion. `Validator` and `Synthesis` are cross-cutting graph stages.

| Agent id | Research mission | Evidence / capabilities required | Asset scope |
| --- | --- | --- | --- |
| `filings` | Inspect primary company filings, statements, footnotes and management commentary | Official filings, disclosures, publication timing | Equity |
| `fundamental` | Growth, cash conversion, margins, leverage, returns on capital, quality of earnings | Point-in-time accounting fundamentals and deterministic ratios | Equity |
| `valuation` | Multiples, sensitivity analysis, scenarios and valuation assumptions | Price, enterprise value, estimates, accounting metrics | Equity |
| `industry` | Economics of the sector, positioning, peers, moats and competitive changes | Sector reports, competitors, company information | Equity/ETF |
| `macro` | Rates, inflation, liquidity, economic regime, FX and policy | Central banks, official time series, market data | Multi-asset |
| `news` | Recent events, future catalysts, event chronology, source credibility | Dated news, official press releases and calendars | Multi-asset |
| `technical` | Trend, momentum, support/resistance, volatility, swings and screening | Deterministic OHLCV/indicators; future SysTrd read-only adapter | Multi-asset |
| `sentiment` | Market positioning, derivatives, flows and sentiment | Futures positioning, derivatives/flow data, suitable sources | Multi-asset |
| `crypto_onchain` | Protocol fundamentals, tokenomics, issuance, networks and on-chain metrics | Auditable blockchain/project/market sources | Crypto |
| `etf` | Composition, fees, concentration, tracking, liquidity and methodology | Issuer documentation, holdings and ETF market data | ETF |
| `backtest` | Historical robustness of precisely specified, deterministic signals | Price histories, strategy specifications and reproducible engines | Multi-asset |
| `risk` | Independent counter-thesis, invalidation conditions, key data gaps and tail risks | Claims and sources from other agents plus independent challenge research | Multi-asset |

**Status in current scaffold:** all specialists are `not_implemented`. The catalogue does not claim research is already running.

## Orchestrator policy

1. Resolve instrument identity. A ticker is insufficient when exchanges or instruments conflict.
2. Interpret purpose/horizon (strategic investment, tactical trade, event review, comparison).
3. Select a subset of agents based on asset class and available capabilities.
4. Plan independent parallel research where dependencies permit; valuation must be able to reuse validated fundamental facts.
5. Deduplicate raw sources and identify contradictory claims.
6. Ask specialist follow-ups only for materially relevant gaps under a cost/time budget.
7. Challenge the emerging thesis rather than average optimistic/negative votes.
8. Synthesize a dated, source-backed report, preserving uncertainty and disagreement.

## Outputs expected from each real specialist

- Structured findings with source IDs, dates, units and currencies.
- Bull case, bear case, main unknowns and identifiable invalidation triggers where applicable.
- Clear separation of observations, estimates and inferences.
- Missing data and coverage limitations.
- No invented numerical scores or unjustified probability/confidence percentage.

## Research vs decision vs execution

Research: source-based analysis; Decision: user-controlled interpretation and optional decision support; Execution: completely separate, unavailable in this codebase.
