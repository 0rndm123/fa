# Shared data contracts

All public payloads should be JSON-serializable and versioned. Pydantic classes in `src/fa_agents/models.py` implement the first draft.

### ResearchRequest

- `symbol`: security/instrument symbol (uppercase normalized)
- `asset_class`: equity | etf | crypto | commodity | fx | index | other
- `exchange`, `instrument_id`: optional identity disambiguators (future asset resolver)
- `question`, `horizon`: research objective and time horizon
- `as_of`: point in time to which analysis is bounded; missing means latest available
- `include_agents` / `exclude_agents`: specialist control

### Evidence

- `source_id`, `source_name`, `source_url`
- `published_at`: publication time, when known
- `observed_at`: time/period when fact was true
- `retrieved_at`: time the source was accessed
- `text_excerpt`: short attributable excerpt; avoid unlicensed copying

### AgentResult

- `agent_id` and `status`: completed | partial | no_data | not_implemented | failed
- `summary`, `claims`, `evidence`, `limitations`
- Status cannot be `completed` when the underlying specialist did no research.
- Claims should eventually have typed category and linked evidence ids.

### ResearchReport

- `request`, `generated_at`, `status`, `results`, `warnings`
- Initially an *execution status report*. A genuine synthesized investment thesis is **not** implemented.
- Later: scenarios, thesis, disagreements, invalidation triggers, source index and quality assessment.

### Versioning

Introduce `schema_version` before external app integrations. Changes to JSON output must be backwards compatible or versioned. Use common identifiers, asset-class typing and ISO 8601 UTC timestamps.
