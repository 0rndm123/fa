# FA — Financial Analysis Agents

Independent, read-only financial research system using Python, LangGraph and LangChain.

**Status:** architecture and executable orchestration scaffold. The specialist agents are intentionally **not yet implemented**. No financial conclusions or invented online research are returned by the scaffold.

## Objectives

- Analyze equities, ETFs, cryptoassets, commodities, FX and indices through purpose-specific specialist agents.
- Use an orchestrator to select experts, aggregate evidence, challenge assumptions and synthesize a report.
- Start independently of SysTrd; connect later via versioned ports/adapters to SysTrd and other applications.
- Preserve evidence provenance, point-in-time semantics, observable execution and model/provider flexibility.
- Keep all trading/execution operations outside this repository.

## Quick start

```bash
python -m pip install -e ".[dev]"
fa-agent plan --symbol NVDA --asset-class equity
fa-agent run --symbol NVDA --asset-class equity
pytest
```

`plan` selects specialists; `run` exercises the LangGraph workflow but clearly reports each specialist as `not_implemented`.

## Architecture

`Request -> Resolve/Plan -> parallel specialists -> Validation/Challenge -> Synthesis -> ResearchReport`

See [architecture](docs/architecture.md), [specialists](docs/agent_catalog.md), [contracts](docs/contracts.md) and [roadmap](docs/roadmap.md).

## Important security note

This repository is **public**. Do not commit credentials, financial account data, private strategies, customer information or proprietary SysTrd implementation. Use environment variables and local configuration excluded from Git.

## Design principles

1. Research (read-only) is separate from decision support and possible future trade execution.
2. LLMs may request capabilities; they must not execute arbitrary SQL, Python or trading actions.
3. Financial calculations are deterministic, testable tools, not LLM arithmetic.
4. Every material claim needs a source and a valid temporal reference.
5. Missing data and unimplemented capabilities must be reported explicitly, never fabricated.
