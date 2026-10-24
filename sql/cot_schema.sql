-- Optional standalone future PostgreSQL COT mirror. Never applied automatically.
-- Provision a separate DB and READ-ONLY role for FA_Agent.
CREATE TABLE IF NOT EXISTS cot_reports (
    report_type text NOT NULL CHECK (report_type IN ('legacy','disaggregated','tff')),
    contract_code text NOT NULL,
    contract_name text NOT NULL,
    market_name text NOT NULL,
    report_date date NOT NULL,
    published_at timestamptz NULL,
    open_interest bigint NOT NULL CHECK (open_interest > 0),
    source_fields jsonb NOT NULL,
    source_dataset_id text NOT NULL,
    source_record_id text NULL,
    ingested_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (report_type,contract_code,report_date)
);
CREATE INDEX IF NOT EXISTS cot_reports_lookup
    ON cot_reports (report_type,contract_code,report_date DESC);

-- In the future, create a dedicated reader role with SELECT only.
-- Ingestion jobs must preserve CFTC IDs, data revisions and actual release times.
