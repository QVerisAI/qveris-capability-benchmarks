# Provider qualification evidence — 2026-08-06

This record covers the v1 ETF Holdings and Stock Quote candidates below. It records
only configuration and authorization facts; it is not benchmark evidence and makes
no statement about provider task outcomes.

| Provider | Direct Test path | Credential environment variable | Cohort status |
| --- | --- | --- | --- |
| Alpha Vantage | `alphavantage.etf.profile.retrieve` | `QVERIS_API_KEY` | included |
| Fund Insight | `fiu_mcp_server.postapiusf10fundconstituent` | `QVERIS_API_KEY` | included |
| Twelve Data | `twelvedata.etfs.world.composition.retrieve` | `QVERIS_API_KEY` | excluded |
| Financial Modeling Prep | https://financialmodelingprep.com/stable/etf/holdings?symbol=SPY | `FMP_API_KEY` | excluded |
| Finnhub | https://finnhub.io/docs/api/etf-holdings | `FINNHUB_API_KEY` | excluded |
| EODHD | https://eodhd.com/financial-apis/stock-etfs-fundamental-data-feeds | `EODHD_API_TOKEN` | excluded |

The included paths were discovered through QVeris on 2026-08-06 and are frozen as
explicit tool IDs with `QVERIS_API_KEY`; their Provider attribution is retained in
the registry. `qveris_finance.*` automatic-routing tools are intentionally excluded:
they do not provide a stable underlying Provider identity for this benchmark.

Financial Modeling Prep, Finnhub, and EODHD lack a discovered QVeris Direct
ETF-holdings interface in the US scope. They remain excluded until a qualifying
path and authorization are recorded. This record is configuration evidence, not
execution evidence.

Twelve Data was discovered but did not qualify: the 2026-08-06 fixed Direct
diagnostic recorded the same error envelope for its positive and negative controls.
The value-free run provenance and raw-response digests are in
`docs/evidence/qveris-direct-diagnostic-2026-08-06.json`; it is excluded pending
a successful positive control.
