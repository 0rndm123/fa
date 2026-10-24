# Market Data Crew: specialized quote subagents (v0.4)

The market-data crew answers simple natural-language quote questions without launching the full Financial/Technical/News graph.

## Routing rules

1. Detect spot/latest-quote intent, excluding forecasts, targets and historical price analyses.
2. Resolve the instrument from a company name or ticker; otherwise use the symbol selected in the workbench.
3. Select eligible vendor specialists based on asset class.
4. Query those specialists independently in parallel, record failures and preserve provider timestamps and quote currencies.
5. Prefer Yahoo Finance for equities, Binance Spot for crypto; display others as separate comparable results (do **not** average USD and USDT or different venues).
6. Give a precise numeric value only if a provider returns symbol, price, currency and timestamp. Never invent quote values.
7. Return a concise answer plus Quote tab with the selected price, provider comparisons, sources and a chart if timed bars are supplied.

## Yahoo Finance Quote Agent

Uses the Yahoo Finance chart v8 endpoint, which is **undocumented/unofficial** and subject to rate limiting, blocks and changes without notice. Reports the regular-market price and provider timestamp. Realtime feed status is unverified; never label it LIVE without stronger proof.

## Binance Spot Quote Agent

Uses the official public unauthenticated REST endpoint at **data-api.binance.vision/api/v3/ticker/24hr**, which returns lastPrice and closeTime, among other rolling-24h statistics. closeTime is the *rolling-window endpoint timestamp*, not necessarily the precise last trade time. Quotes are explicitly from Binance **Spot**. BTC/USDT is not the same currency quote as BTC/USD.

No private keys or trading permissions are used.

## TradingView Quote Agent

TradingView's official Advanced Charts Datafeed API provides a way for a customer to supply prices **to TradingView charts**. It is not a general public service for extracting TradingView market-data quotes. The FA system does not scrape authenticated TradingView pages.

This specialized agent is ready to read from an **explicit local read-only adapter**, which can later wrap a licensed source or independent TradingView export process.

Optional local adapter configuration:

~~~
FA_TRADINGVIEW_QUOTE_ADAPTER_URL=http://127.0.0.1:some-port
~~~

The adapter must implement \`GET /quote?symbol=<instrument>\` and respond with:

~~~json
{
  "symbol":"NASDAQ:NVDA",
  "name":"NVIDIA Corporation",
  "exchange":"NASDAQ",
  "price":123.45,
  "currency":"USD",
  "quote_time":"2026-10-24T12:30:00Z"
}
~~~

Values above are contract examples, **not real prices**. The FA backend accepts only localhost HTTP endpoints for this adapter and rejects other hostnames. This integration remains inactive until the user supplies a working independent source. No proprietary SysTrd code, authentication or DB access is embedded in FA.

## Scope

Currently this crew provides snapshots and limited Yahoo recent intraday history. Future subagents may handle historical OHLCV, corporate actions, market sessions, symbol lookup, bid/ask and order books, exchange calendars, data quality and licensed feeds. Do not claim any of these are implemented until tests demonstrate it.

The quote subagents do not provide trading advice, and will report source errors or missing data when a feed is unavailable.
