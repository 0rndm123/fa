# Crypto derivatives and BTC/ETH COT (v0.7)

## COT market research
The CFTC TFF futures-only records contain Bitcoin futures and related
contracts. The COT agent searches BITCOIN and ETHER futures contract market
names and requires the user to select the precise futures contract when
multiple candidates are returned. It does not re-label CME futures trader
categories as global cryptocurrency market positions.

## Binance Futures specialist
The separate Crypto Derivatives analyst uses three public Binance USD-M
Futures endpoints:
- GET /fapi/v1/fundingRate, funding rate settlement history, in percent
  *per funding interval*, allowing negative values.
- GET /fapi/v1/openInterest, a current snapshot in base asset units,
  not USD notional or historical open interest.
- GET /futures/data/globalLongShortAccountRatio, ratio of LONG to SHORT
  accounts, not contract exposure or overall long-short notional.

No private account endpoints, trading permissions or exchange API keys.
Partial outages are reported and other sources remain inspectable.

## Workbench examples
With Live mode and Crypto asset class:
- COT do Bitcoin -> futures contract selection and CFTC COT tab
- COT do ETH -> CFTC contract search and COT tab
- Qual o funding do BTC? -> Binance Crypto Derivatives tab
- Open interest e long/short do ETH -> separate timestamped metrics and charts

The two crews are independent: CFTC categories are not comparable with
perpetual funding or Binance customer account ratios.

## Future PostgreSQL
CryptoDerivativesSource defines the replacement read interface for a
future dedicated read-only PostgreSQL adapter. Neither tables nor
credentials are created now. The future schema should track vendor,
venue, contract, metric, units, event/retrieval timestamps and revisions.
Do not construct historical open interest from a current snapshot.
