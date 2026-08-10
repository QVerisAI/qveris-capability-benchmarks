# Provider access and billing sources — 2026-08-10

This record contains time-bounded facts taken from official supplier pages. Supplier
list prices and QVeris gateway observations are independent facts: a supplier plan
must not be interpreted as the cost of a QVeris call.

## Official billing

| Provider | Scope | Original currency | Free access | Paid entry point | Official source | Source SHA-256 |
| --- | --- | --- | --- | --- | --- | --- |
| Alpha Vantage | Provider API plans | USD | 25 API requests/day | Premium from USD 49.99/month | [Premium](https://www.alphavantage.co/premium/) | `8c1c5dc3b6635a7d3d58f64378fab701c4d8ec5f122302aa00981aa81da90baa` |
| Twelve Data | Provider API plans | USD | Basic: 8 API credits/minute, 800/day | Grow from USD 29/month | [Pricing](https://twelvedata.com/pricing) | `00bd84cd0b0d9ce97da479e2a5ebfa25365bc3efa46f7b27c53f8384cb80f27d` |
| EODHD | Provider API plans | USD | 20 API calls/day | All-in-One USD 99.99/month | [Pricing](https://eodhd.com/pricing) | `3e9250bf0e6934ad97e93fd10f0ad9274d68a0ba26f965324daa296394191b5f` |
| Financial Modeling Prep | Provider API plans | USD | Basic: 250 calls/day | Starter USD 22/month when billed annually | [Pricing](https://site.financialmodelingprep.com/pricing-plans) | `62e6030f78a90cc15d6b099ef5e962a17650022f153224ef940157aee7dc2466` |
| Finnhub | Provider API plans | USD | Free: 60 API calls/minute | All-in-One USD 3,500/month, billed annually | [Pricing](https://finnhub.io/pricing) | `eff357486ad4802751226f48e174112d051fe38f6ff99785b3c46903bc01bc49` |
| Fund Insight | Institutional service | Not published | No public free API tier | Institutional pricing under a separate MSA | [Terms](https://www.fundinsight.net/terms-of-service) | `e39cc2a04ce753572ba7a3bc9d087d66d54094d8055fff1c22fb1d591be6790c` |
| Massive Stocks | Stocks product | USD | Stocks Basic: USD 0, 5 API calls/minute | Stocks Starter USD 29/month | [Pricing](https://massive.com/pricing?product=stocks) | `74c0b1e200eb072becdfb0463056f7dcb498f7cebae8df65480d46792a2255de` |
| SEC EDGAR | Public API | Not applicable | Public API with no fee or API key | No paid plan | [EDGAR APIs](https://www.sec.gov/search-filings/edgar-application-programming-interfaces) | `e711d1dbf5dfc4f75ee9af64c875c7dbc71006348d59bc76525b3066440b74e4` |
| 融聚汇 | Custom API | Not published | No public free API tier | Custom commercial quote | [API 定制服务](https://www.szfiu.com/custom/detail.php?id=api) | `572259dc17bc81754171295b0741769aaefa921306093d0e4007ca7939affdce` |
| Narodowy Bank Polski | Public Web API | Not applicable | Public API with no fee or API key | No paid plan | [NBP Web API](https://api.nbp.pl/en.html) | `57b5c30f7712b7d94520d302b07321a485b6e92fac08d4b036240c02d1833f7e` |
| 同花顺 iFinD | Native MCP plans | CNY | New accounts receive 2,000 trial requests | Personal CNY 40/month for 5,000 requests; Enterprise CNY 5,000/month for 1,000,000 requests | [MCP pricing](https://mcp.51ifind.com/?syncCookieTimes=1#/pricing) | `d8621d75747f02e66b4d054d4884a53b86eece43c0966af697215b1856616c00` |

The verification protocol fingerprint is
`66900ca1b6678662e47832dfb020e9cf546b4425ca9d4acda5b731b14202261f`.
It requires an official URL, applicable product or Access Path scope, original
currency, free-tier statement, paid-plan statement, verification date, and content
digest. A home page, documentation page, or inquiry form is not converted into a
numeric price when the official source does not publish one.

## Official native machine access

| Provider | Protocol and endpoint | Authentication | Official source |
| --- | --- | --- | --- |
| Alpha Vantage | HTTPS REST at `https://www.alphavantage.co/query` | API key query parameter | [API documentation](https://www.alphavantage.co/documentation/) |
| Twelve Data | HTTPS REST at `https://api.twelvedata.com` | API key query parameter or header | [API documentation](https://twelvedata.com/docs) |
| EODHD | HTTPS REST at `https://eodhd.com/api` | API token query parameter | [API documentation](https://eodhd.com/financial-apis/) |
| Financial Modeling Prep | HTTPS REST at `https://financialmodelingprep.com/stable` | API key query parameter | [Stable API documentation](https://site.financialmodelingprep.com/developer/docs/stable) |
| Finnhub | HTTPS REST at `https://finnhub.io/api/v1` | API key query parameter or header | [API documentation](https://finnhub.io/docs/api) |
| Fund Insight | FIX 4.4 endpoint disclosed under a customer MSA | MSA-issued credentials | [Terms](https://www.fundinsight.net/terms-of-service) |
| Massive Stocks | HTTPS REST at `https://api.massive.com` | API key | [Stocks REST API](https://massive.com/docs/rest/stocks/overview) |
| SEC EDGAR | HTTPS REST at `https://data.sec.gov/api/xbrl/companyfacts` | No API key; SEC-compliant `User-Agent` required | [EDGAR APIs](https://www.sec.gov/search-filings/edgar-application-programming-interfaces) |
| 融聚汇 | Endpoint disclosed during commercial onboarding | Contract-issued credentials | [API 定制服务](https://www.szfiu.com/custom/detail.php?id=api) |
| Narodowy Bank Polski | HTTPS REST at `https://api.nbp.pl/api` | No authentication | [NBP Web API](https://api.nbp.pl/en.html) |
| 同花顺 iFinD | MCP Streamable HTTP at the official stock MCP service | Raw `Authorization` header value | [Official skill install guide](https://mcp.51ifind.com/gwstatic/static/ds_web/ifind-mcp-web/skills/SKILL_INSTALL_GUIDE.md) |

Native and QVeris Access Paths remain distinct benchmark identities and use distinct
run keys. This public record does not store benchmark credentials or managed QVeris
execution endpoints.
