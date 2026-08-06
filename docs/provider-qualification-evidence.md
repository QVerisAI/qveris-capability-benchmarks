# Provider qualification evidence — 2026-08-06

This record covers the v1 ETF Holdings and Stock Quote candidates below. It records
only configuration and authorization facts; it is not benchmark evidence and makes
no statement about provider task outcomes.

| Provider | Official interface source | Credential environment variable |
| --- | --- | --- |
| Alpha Vantage | https://www.alphavantage.co/documentation/ | `ALPHA_VANTAGE_API_KEY` |
| Financial Modeling Prep | https://financialmodelingprep.com/stable/etf/holdings?symbol=SPY | `FMP_API_KEY` |
| Finnhub | https://finnhub.io/docs/api/etf-holdings | `FINNHUB_API_KEY` |
| EODHD | https://eodhd.com/financial-apis/stock-etfs-fundamental-data-feeds | `EODHD_API_TOKEN` |
| Twelve Data | https://twelvedata.com/docs | `TWELVE_DATA_API_KEY` |

At the time of this record, no QVeris-controlled credential or explicit benchmark
execution authorization was present for these paths. Each is therefore excluded
from the frozen cohort. A later inclusion requires a new terminal qualification
decision backed by authorization and successful Direct Test evidence; it must not
reuse this record as execution evidence.
