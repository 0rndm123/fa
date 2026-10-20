# Architecture | FA independent research service

## Boundaries

FA is a stand-alone application. It MUST NOT import from SysTrd or depend on its schema, folder layout, scheduler, database, authentication or runtime.
Integration happens later through read-only provider adapters or a documented API. Other consumer applications receive the same service contracts.
Financial research is **not** trade execution. No broker / exchange order tools should be present here.

## Logical components

```text
CLI / future Web UI / future external apps
           |
        Public API (future)
           |
    Request validation + Asset resolution
           |
    Orchestrator (LangGraph StateGraph)
           | choose capabilities, control budget, timeouts, retries
           +---> Filing/SEC ------+
           +---> Fundamental -----+
           +---> Valuation -------+
           +---> Industry --------+
           +---> Macro -----------+--> Evidence validation --> Challenger/Risk --> Synthesis
           +---> News/Catalysts --+                             |
           +---> Technical -------+                       ResearchReport
           +---> Sentiment -------+
           +---> Crypto/ETF ------+
           +---> Backtest --------+
           |
     Capability Registry / Ports
           |
 Online APIs / filings / news | local files | future SysTrd | other apps
```

A research orchestration graph uses deterministic routing by default. LLMs specialize in interpreting evidence, assessing hypotheses and writing grounded synthesis; they do not directly generate SQL or execute Python.
A future model-based planner may propose a plan but it must be validated against the registered capability allowlist.

## Internal packages

- `models.py`: versionable request, evidence, agent result and final report schemas.
- `catalog.py`: available expert identities, asset-class routing rules.
- `ports.py`: external search, fundamentals, technical data and research storage interfaces.
- `graph.py`: real LangGraph plan/fan-out/validation/synthesis scaffold.
- `cli.py`: local usage and smoke-test entry point.

When the first real specialist is implemented, refactor the specialist placeholder into isolated agents and tools under `agents/` and `tools/`; avoid premature nesting.

## Execution and reliability requirements

- Each run has a unique id; explicit asset identity (symbol **plus** optional venue/ISIN/chain/network).
- Parallel specialists should share **immutable facts**, not overwrite one another's answers.
- Configure limits for max requests, web calls, model tokens, total cost, elapsed time and follow-up iterations.
- Distinguish transient failure, missing data, unsupported asset, and unimplemented agent.
- Checkpoint graph progress separately from durable research history. SQLite locally first if needed; Postgres later.
- Raw source, extracted fact, analyst interpretation and forward scenario are different record types.
- Record observation/effective date, publication date, retrieval date and analysis-as-of date. Point-in-time validity is mandatory for historical studies.
- Capture source URL, publisher and how evidence was used. Never treat generated prose as a primary source.
- Human review before converting analysis into trading decisions.

## Integration contract

Future interfaces (read-only initially):
- `POST /v1/research`: submit `ResearchRequest`
- `GET /v1/research/{run_id}`: status and structured `ResearchReport`
- `GET /v1/capabilities`: registered agent/tool capabilities

Those routes are **planned**, not implemented. SysTrd and other applications must call the same versioned interface or supply adapters implementing the ports. No coupling to SysTrd's internal tables in the domain layer.

## LLM and models

LangGraph coordinates graph/state. LangChain provides model and tool integrations when research tools are implemented. Provider and model must be configurable, never hardcoded to one vendor. Do not store API credentials, personal portfolios or private strategies in this public repository.
