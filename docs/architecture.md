# FA_Agent | Standalone multi-agent architecture, v0.2

## Isolation

This project is independent of SysTrd and other applications. No imports from them, no required PostgreSQL and no trading or brokerage capabilities. Future external integrations use read-only service/adapter contracts.

## Current executable pipeline

Request -> deterministic Plan -> dynamic Send fan-out (LangGraph specialists)
-> Validate coverage -> rules-based Risk Review -> JSON report.

Specialist workers run independently and share a deterministic, versioned report contract. The Risk Reviewer sees all specialist results before producing coverage warnings. Other specialist-to-specialist delegation is a future capability, not implemented today.

## Implemented research capabilities

- Fundamental (US SEC companyfacts 10-K annual XBRL, deterministic ratios).
- Filings (SEC submissions links and form/date metadata; not document text).
- News (current Google News RSS headlines; no article full text verification).
- Technical (user-provided date/close CSV, close and simple moving averages).
- Risk (coverage checks; independent challenger research is not implemented).
- LangChain commentary is optional when a user locally sets OPENAI_API_KEY; it only sees collected records and cannot independently fetch sources.

Everything else listed in agent_catalog.md remains an explicit not_implemented placeholder.

## Source and temporal integrity

Each Evidence record identifies an external URL or explicitly describes a local input or synthetic fixture. Published, observed and retrieved timestamps are separate. SEC facts are filtered on filed and period-end dates, avoiding simple point-in-time hindsight; historical ticker identity is not yet guaranteed. RSS historical searches are explicitly rejected.

All opinions, scores and financial calculations must be traceable. Never mistake a news headline for a verified reported event or a filing URL for a read filing.

## Extensibility

- providers.py: SEC, RSS, CSV and offline synthetic fixtures.
- agents.py: deterministic financial/technical workers and rules-based review.
- catalog.py: agent identities and selection policy.
- graph.py: LangGraph lifecycle and injectable Services.
- models.py: public Pydantic contract.
- llm.py: optional LangChain narrative layer.
- cli.py: user-facing command.
- ports.py: future provider/service protocols (not wired into production yet).

Later: proper Security Master, specialized financial agents, actual historical news, quantitative testing, data-source permission boundaries, provider-specific budget controls, persistable checkpoints, independent challenger and versioned REST API. The SysTrd adapter can only supply structured data; it must not alter the FA domain architecture.

## Security

All external research is read-only. API keys and private data remain local. This repository is public. Financial documents or external content are untrusted instructions to any LLM.
