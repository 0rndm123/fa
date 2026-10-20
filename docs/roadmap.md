# Roadmap | progressive delivery

## Stage 0 — Repository skeleton [created]

- [x] Independent project and Python package layout
- [x] Typed contracts, specialist registry and asset-aware routing
- [x] LangGraph plan / parallel worker / validate / synthesize *scaffold*
- [x] CLI and structural tests
- [x] Extension ports for data providers
- [ ] Real source retrieval / live research / analytical outputs

## Stage 1 — First factual vertical slice

- [ ] Identity resolution, starting with listed equities and ambiguous tickers
- [ ] Online source adapter, dated search results, source-quality tagging and caching
- [ ] Implement News and Filings/Fundamental specialists with structured output
- [ ] Independent Risk/Challenger research plus source-linked synthesis
- [ ] Tests with known fixtures, contradiction and missing-source scenarios
- [ ] End-to-end report for one equity without manual enrichment

## Stage 2 — Deeper analysis

- [ ] Valuation, industry and macro specialists
- [ ] Configurable LangChain model factory and prompt versioning
- [ ] Real retries, budgets, observability, run history, persistence and checkpoints
- [ ] User-facing report / CLI improvements and optional standalone API

## Stage 3 — Multi-asset and external interoperability

- [ ] Crypto, ETF, positioning/sentiment and technical specialists
- [ ] Read-only SysTrd adapter through a versioned service API, no direct table imports
- [ ] Optional adapters for other applications and data stores
- [ ] Comparative / portfolio-level research and scheduling

## Stage 4 — Measurement

- [ ] Point-in-time backtesting of **dated theses** and reproducibility
- [ ] Compare conclusions with realized outcomes without future leakage
- [ ] Evaluate source reliability, specialist value-add, latency and cost

Implementation stages are priorities, not timelines or commitments.
