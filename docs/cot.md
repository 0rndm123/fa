# COT Agent v0.6 — Source abstraction and PostgreSQL roadmap

## Reporting families
Official CFTC Public Reporting Socrata API, futures-only:
- TFF gpe5-46if: Dealers, Asset Managers, Leveraged Money and others.
- Disaggregated 72hh-3qpy: Producers/Merchants, Swap Dealers, Managed Money, others.
- Legacy 6dca-aqww: Commercial, Non-Commercial and Non-Reportables.

NEVER equate or combine report families or mix futures-only with futures-and-options-combined.
CFTC report dates reflect Tuesday positioning and are typically published on Friday.
For backtests, report_date is NOT an availability timestamp; reconstruct release times first.

## Using the local app
In Live, ask "COT do ouro", "COT do petróleo", "COT do Nasdaq 100".
The agent discovers matching contract markets. If multiple contracts match, the COT tab offers an explicit CFTC contract-code picker and reruns on the chosen contract.
An individual equity like NVDA has no default COT contract mapping.
When an exact contract is established, it returns up to 52 weeks of trader net positions (long minus short), net as % open interest, weekly changes, source references, a chart and table.

## Providers
The CotSource protocol isolates the provider via search(report_type,term) and history(report_type,market_code,limit).
- CftcApiSource implements read-only official HTTPS queries; no credential required.
- PostgresCotSource is a future optional SELECT-only adapter; not active without a PostgreSQL database.
- The standalone optional schema is sql/cot_schema.sql, which is NOT deployed or populated by FA_Agent.

Future connection, only after the user creates the dedicated DB:
    python -m pip install -e ".[cot_pg]"
    $env:FA_COT_SOURCE = "postgres"
    $env:FA_COT_PG_DSN = "<a separately managed read-only connection string>"

No SysTrd dependency or access to the user's existing database is assumed.
CFTC API outages/ambiguity and incomplete source rows must be exposed rather than filled with guesses.
Avoid deriving trading signals from weekly COT net positions without statistical testing.
