# FA_Agent | Contracts v0.2

Implemented in src/fa_agents/models.py using Pydantic.

## ResearchRequest

symbol, asset_class, exchange (optional), instrument_id (optional), question, horizon, as_of, include_agents and exclude_agents.

asset_class: equity | etf | crypto | commodity | fx | index | other.

Symbol does not uniquely identify an instrument worldwide; exchange and instrument_id are reserved for disambiguation. Only US SEC ticker lookup exists in the current source provider.

## Evidence

source_id, source_name, source_url, retrieved_at, published_at, observed_at, text_excerpt, is_synthetic.

- For SEC numerical data, observed_at is the financial period end; published_at is the filing date.
- News records are RSS headline metadata only.
- For local CSVs, the source_url is a placeholder and the data source is identified as local/unverified.
- Demo source records explicitly set is_synthetic=true.

## AgentResult

agent_id, status, summary, claims, metrics, evidence, limitations.

status: completed | partial | no_data | not_implemented | failed.

Completed does not mean a buy/sell recommendation. Filings, news, technical and risk agents are partial until their independent methodologies are substantially implemented.

## ResearchReport

schema_version = 0.2; request, generated_at, status, data_mode, planned_agents, results, summary, llm_commentary (optional), warnings.

Report status is coverage-dependent. The optional LLM commentary is not an additional source of verifiable evidence.

Future schemas should introduce explicit metric units, source IDs per financial claim, per-agent version and source snapshots before historical thesis evaluation.
