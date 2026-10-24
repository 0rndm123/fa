# FA_Agent implementation roadmap

## Delivered in v0.2
- Typed request/response/evidence schemas, independent repository and 12-agent catalogue.
- LangGraph specialist fan-out, deterministic review, synthesis and CLI.
- Working source adapters to SEC annual company facts, SEC filings metadata and current Google News RSS headlines.
- CSV-based technical computations and explicit source/temporal limitations.
- Synthetic no-key demo with automated tests and GitHub Actions.
- Optional LangChain OpenAI narrative on the already collected evidence.

## Next functional increments
1. Extract/read filings text including management discussion and footnotes, verify source passages.
2. Distinct financial subagents: profitability, liquidity, debt, cash generation and valuation; avoid duplicated data retrieval.
3. Real sector and peer research, common issuer identifiers and industry taxonomies.
4. Live technical OHLCV provider with adjusted-price metadata, configurable timeframes, indicators, swing research.
5. Independent risk/challenger research, scenarios, contradictions and evidence traceability.
6. Report renderer, comparisons, historical memory, caching and budget controls.
7. Standalone versioned REST API, then optional read-only adapters to SysTrd or other apps.
8. Point-in-time thesis and strategy evaluation without hindsight or selection biases.

A catalogue entry is never considered an implemented agent until tested with real sources and assertions.
