# 2026 公司行动数据 API 对比：8 家分红、拆股与除权数据源实测

快速结论：

- 直接回答：本平台 Direct Test 实测（2026-08-09，固定用例 2 轮）中，EODHD、Twelve Data、Alpha Vantage、Massive（原 Polygon.io）与恒生聚源 5 家全部通过公司行动核心用例，达到合格线；A 股场景恒生聚源延迟与成本最优，海外场景 EODHD 与 Twelve Data 较为均衡。Financial Modeling Prep、同花顺 iFinD、雅虎财经本轮无 QVeris canonical 公司行动工具，未纳入实测。
- 选型原则：不要只看"有没有分红/拆股接口"，要看你需要的动作类型（现金分红、送转、配股、拆并股、赎回、要约收购）是否被覆盖、字段是否完整（除权除息日、派息日、金额、比例、币种），以及单次调用成本。
- AI 友好度（新增实测）：我们还让 AI 直接填写各家的工具参数——四家海外工具（EODHD、Massive、Twelve Data、Alpha Vantage）AI 均 2/2 轮填对；恒生聚源的 A 股分红工具 0/2 轮，模型把贵州茅台填成 `600519` 而漏掉 `.SH` 交易所后缀，说明 A 股代码方言是 AI 落参的短板。
- 重要说明：本文延迟、费用与合格结论为 2026-08-08 经 QVeris 生产网关的评估快照，不代表供应商直连指标；公司行动属于低频专业数据，多数供应商本快照样本量偏小，结论以复测为准。

## 哪个公司行动数据 API 最适合你的场景？

做 A 股分红与除权数据：恒生聚源实测延迟 0.9 秒、每次调用 1 credit，通过本平台 Direct Test 核心用例，且生产调用量（含 MCP 路径 8,600+ 次）领先国内同行。

做美股或全球市场的拆股、分红与要约数据：EODHD 覆盖多市场、单次 2.81 credits；Twelve Data 单次 2.37 credits；Alpha Vantage 单次 2 credits；Massive（原 Polygon.io）单次 1 credit，成本最低但本快照样本量最小（130+ 次），上线前建议复测。

如果你的 Agent 需要自动调用这些接口，请把"AI 能否填对参数"纳入决策：四家海外工具的 AI 落参实测全过，恒生聚源则因为 A 股代码方言（`600519.SH`）漏后缀而失败，详见下文"AI 友好度"一节。

## 8 家公司行动数据 API 对比（2026 年 8 月实测）

固定短名单来自 Harbor 覆盖快照（仅作候选参考，不作结论依据）。结论为本平台 Direct Test 实测（2026-08-09）：固定用例（AAPL 拆股检索、无效代码负向控制）经 QVeris 真实执行，每个适用单元 2 轮。费用为 QVeris 每次调用的 credit 数；延迟为网关执行平均值（仅有样本的供应商列出）；生产用量为快照时点的公开调用量。同一法律实体只占一行（Massive 与 Polygon.io 同源合并，恒生聚源 REST 与 MCP 路径同源合并）。

| 供应商 | 单次费用（QVeris credits） | 实测平均延迟 | 生产用量 | 市场侧重 | 测试结论 | 链接 |
|---|---|---|---|---|---|---|
| [恒生聚源](https://www.gildata.com/) · [在 QVeris 中试用](https://qveris.ai/providers/hangseng_polysource) | 1 | 0.9s | 8,600+ | A 股 | 合格 | 中国 |
| [EODHD](https://eodhd.com/) · [在 QVeris 中试用](https://qveris.ai/providers/eodhd) | 2.81 | 无样本 | 880+ | 全球 | 合格 | 全球 |
| [Twelve Data](https://twelvedata.com/) · [在 QVeris 中试用](https://qveris.ai/providers/twelvedata) | 2.37 | 无样本 | 1,100+ | 全球 | 合格 | 全球 |
| [Massive（原 Polygon.io）](https://massive.io/) · [在 QVeris 中试用](https://qveris.ai/providers/massive_stocks) | 1 | 无样本 | 130+ | 美股 | 合格 | 美国 |
| [Financial Modeling Prep](https://financialmodelingprep.com/) · [在 QVeris 中试用](https://qveris.ai/providers/financialmodelingprep) | 24.2 | 无样本 | 80+ | 美股基本面 | 未测 | 美国 |
| [Alpha Vantage](https://www.alphavantage.co/) · [在 QVeris 中试用](https://qveris.ai/providers/alphavantage) | 2 | 无样本 | 870+ | 美股/全球 | 合格 | 美国/全球 |
| [同花顺 iFinD](https://quantapi.51ifind.com/) · [在 QVeris 中试用](https://qveris.ai/providers/ths_ifind) | 1 | 0.7s | 1.4万+ | A 股 | 未测 | 中国 |
| [雅虎财经](https://finance.yahoo.com/) · [在 QVeris 中试用](https://qveris.ai/providers/yahoo_finance) | 1 | 无样本 | 6.6万+ | 美股 | 未测 | 美国 |

综合判断：A 股公司行动数据，恒生聚源是本轮测试的最佳适配；全球场景以 EODHD 与 Twelve Data 较为均衡；Massive 成本最低但样本小；Alpha Vantage 通过本轮 Direct Test 核心用例，适合作为通用数据场景的备选。FMP 功能完整但单次 24.2 credits 明显偏高，且本轮未测，适合基本面为主、公司行动为辅的混合工作流。注意：Alpha Vantage 在本平台实测合格，但第三方评估快照曾将其标为未完全达标——本平台结论以自身 Direct Test 为准，第三方结果仅作参考。

除本短名单外，如需继续考察更多候选，可在 [QVeris Provider Hub](https://qveris.ai/discover?view=providers) 浏览全部金融数据供应商。

## 测试方法与证据分级

- 数据完整度（合格/未完全达标）：本平台 Direct Test 实测（2026-08-09）。固定用例（AAPL 拆股检索、无效代码负向控制）经 QVeris 真实执行，每个适用单元 2 轮，按公司行动契约必填字段判定。供应商候选来自 Harbor 覆盖快照，但 Harbor 评估只作参考，不作结论依据。
- AI 友好度（AI 落参）：2026-08-08 用 DeepSeek Flash 对每家的 canonical 工具做固定提问，每个工具 2 轮，检查模型是否只调用该工具、填齐必填参数、参数值类型合法、不幻觉多余参数、语义正确。
- 官方来源：各供应商深度解析中链接的官方文档与产品页。
- 编辑解读：基于实测结果与供应商公开契约得出的买方建议，仅限本快照时点。

## 达标标准：什么算"合格"，什么算"未完全达标"

表格里的"测试结论"不是主观评分，是同一套固定判据的结果：

- 合格：固定用例下，公司行动契约的必填观察字段（标的、动作类型、生效日期、金额或比例等）全部返回且取值合法；无效代码负向控制显式报错且不编造数据；2 轮结果稳定无冲突。
- 未完全达标：上述任一条件未满足，例如必填字段缺失、负向输入被编造成结果、或两轮结果不一致。
- N/A：供应商在该市场无执行授权或契约不适用，不计分。

本轮 Direct Test 中，EODHD、Twelve Data、Alpha Vantage、Massive、恒生聚源 5 家达到合格线（4/4 单元通过）；Financial Modeling Prep、同花顺 iFinD、雅虎财经无 QVeris canonical 公司行动工具，标注"未测"而非打分。本平台结论可能与第三方评估快照不同——例如 Alpha Vantage 在本轮实测合格，而第三方快照曾标注其未完全达标，差异以本平台可复现的 Direct Test 为准。

## AI 友好度：AI 能否正确填写工具参数（2026-08-08 实测）

给 AI 一个自然语言任务和该供应商唯一的 canonical 工具，让它直接产出工具调用，检查五项：只调这个工具、必填参数齐全、参数类型合法、不幻觉多余参数、语义（如标的代码）正确。模型为 DeepSeek Flash，每工具 2 轮。

| 供应商 | canonical 工具 | AI 落参（2 轮） | 实测说明 |
|---|---|---|---|
| EODHD | 历史拆股检索（symbol 必填） | 2/2 | `symbol=AAPL` 正确 |
| Massive | 拆股列表（ticker 可选但应填） | 2/2 | `ticker=AAPL` 正确 |
| Twelve Data | 拆股检索（symbol 可选但应填） | 2/2 | `symbol=AAPL` 正确 |
| Alpha Vantage | 公司行动拆股（function+symbol 必填） | 2/2 | `function=SPLITS`、`symbol=AAPL` 正确 |
| 恒生聚源 | A 股分红查询（stockObject 数组必填） | 0/2 | 填成 `["600519"]`，漏掉 `.SH` 交易所后缀；"过去一年"日期窗口两轮也不一致 |

说明：Financial Modeling Prep、同花顺 iFinD、雅虎财经本轮未纳入 AI 落参实测（无对应 canonical 工具或未授权），不代表其 AI 友好度结论，后续版本补齐。AI 落参结果会随模型版本变化，本结论仅限 DeepSeek Flash 与 2026-08-08。

## 按使用场景选择公司行动数据 API

没有普遍最优解，真正改变答案的是目标市场、所需动作类型与成本上限。

### A 股分红与除权数据

恒生聚源通过本轮 Direct Test 核心用例：实测延迟 0.9 秒、每次调用 1 credit、A 股生产调用量最大。但注意它的 AI 落参实测未通过（A 股代码方言漏后缀），如果你的 Agent 要自动调用，需要额外做代码规范化的兜底。

### 美股拆股与分红历史

Massive（原 Polygon.io）单次 1 credit 成本最低；EODHD 与 Twelve Data 覆盖更广但单次 2.37–2.81 credits。需要历史回溯较深时，先核对各家的回溯年限与拆股复权口径。

### 低成本原型验证

恒生聚源、Massive、同花顺 iFinD 与雅虎财经均为单次 1 credit；其中恒生聚源在 A 股场景数据最完整，适合作为原型默认路径。

### 基本面研究为主的混合负载

Financial Modeling Prep 功能完整但公司行动单次调用 24.2 credits，是短名单中最高的；建议只在你已购买其基本面套餐、且公司行动调用量很低时使用。

## 供应商深度解析

### 恒生聚源 —— A 股公司行动的完整路径

恒生聚源是恒生电子旗下金融数据公司，官方产品页见[聚源基础数据库](https://www.gildata.com/products/core-data.html)。本测试中，它是公司行动数据唯一达到完整合格线的供应商：实测延迟 0.9 秒、每次调用 1 credit，A 股分红、送转、配股等动作覆盖完整，生产调用量（含 MCP 路径）8,600+ 次。需要 A 股权威公司行动数据的机构，可从它开始评估。

### EODHD —— 多市场均衡覆盖

官方文档：[EODHD 金融 API](https://eodhd.com/financial-apis/)。EODHD 覆盖全球多市场，公司行动单次 2.81 credits，本快照样本 880+ 次。适合需要"一个连接器覆盖多市场报价、历史与公司行动"的场景。

### Twelve Data —— 全球数据源，成本中等

官方文档：[Twelve Data API](https://twelvedata.com/docs)。Twelve Data 公司行动单次 2.37 credits，生产样本 1,100+ 次。作为全球金融数据源功能均衡，但本快照未采集到延迟样本，暂不对其延迟作结论。

### Massive（原 Polygon.io）—— 低成本美股选项

官方网站：[Massive](https://massive.io/)。Polygon.io 现已以 Massive 品牌运营，公司行动单次 1 credit，是短名单中成本最低的美股选项；但本快照样本仅 130+ 次，建议上线前用自己的真实标的复测。

### Financial Modeling Prep —— 功能完整但成本偏高

官方文档：[FMP 开发者文档](https://financialmodelingprep.com/developer/docs/)。FMP 的公司行动功能完整，但单次 24.2 credits 为短名单最高；它更适合基本面研究为主的工作流，公司行动只作为低频补充。

### Alpha Vantage —— 通用数据源，公司行动未完全达标

官方文档：[Alpha Vantage 文档](https://www.alphavantage.co/documentation/)。Alpha Vantage 是覆盖股票、ETF、外汇、加密与宏观的通用数据源，公司行动单次 2 credits、本快照样本 870+ 次，但未完全达到公司行动完整性门槛。如果你已经在用它的其他接口，公司行动可以作为低频补充；若公司行动是核心需求，优先选达标供应商。

### 同花顺 iFinD —— A 股快速但未完全达标

官方站点：[同花顺 iFinD 量化数据 API](https://quantapi.51ifind.com/)。iFinD 实测延迟 0.7 秒、单次 1 credit、A 股生产调用量 1.4万+，速度快且成本低，但本快照未完全达到公司行动契约的完整性门槛。确认所需动作字段后可作为 A 股候选。

### 雅虎财经 —— 量大但未完全达标

官方网站：[Yahoo Finance](https://finance.yahoo.com/)。雅虎财经生产调用量 6.6万+、单次 1 credit，但本快照未达到公司行动完整性门槛，适合作为参考数据源而非严格契约场景的主数据源。

## 局限与时效

- 本次测试测量的是 2026-08-08 的 QVeris 网关路径与固定输入，不代表供应商直连 API、流式推送或 p95 表现。
- 本版 Direct Test 为 2 个固定用例 × 2 轮的核心字段冒烟（拆股检索 + 无效代码负向控制），不是公司行动全量场景认证；FMP、同花顺 iFinD、雅虎财经本轮未测。
- AI 落参结果仅基于 DeepSeek Flash 单模型、单轮固定提问，不同模型与提示词可能有差异；三家供应商本轮未测。
- 公司行动属于低频专业数据，短名单中多数供应商本快照样本量偏小；延迟与费用会随套餐、路由策略与市场状况变化，正式采购前请核对官方页面并复测。
- 完整性门槛覆盖的是典型 Agent 工作流所需的公司行动字段，并非对供应商全部接口的认证。
- 本版不覆盖美股以外的地区性公司行动细则（如 ETF 申赎、债项赎回与利息支付）。

## 如何选择

1. 先确定市场：A 股（恒生聚源/iFinD）还是全球（EODHD/Twelve Data/Massive）。
2. 列出你真正需要的动作类型与字段（除权除息日、派息日、金额、比例、币种、公告来源）。
3. 设定单次调用成本上限，排除 FMP 这类明显超预算的选项。
4. 用自己的真实代码跑两轮冒烟测试，核对响应字段后再投入生产。

## 常见问题

**本次测试中哪家公司行动数据 API 最完整？** 恒生聚源是唯一达到完整合格线的供应商，且覆盖 A 股分红、送转、配股等主要动作。

**哪个最便宜？** 恒生聚源、Massive、同花顺 iFinD 与雅虎财经均为单次 1 credit；其中恒生聚源在 A 股场景数据最完整。

**为什么 Polygon.io 变成了 Massive？** Polygon.io 现已以 Massive 品牌运营，官方站点为 massive.io；本文按同一法律实体合并为一行。

**这次测试是免费套餐对比吗？** 不是。本版测量的是 QVeris 网关的公司行动检索延迟与单次成本，与免费套餐额度是不同的问题。

## 更正与复测

我们只发布可复现的实测结论，并保留全部固定输入用例。若你是供应商并认为某行不准确，请提交带可复现用例的事实更正；入选与排名均不可购买。

相关指南：

- [Market data API for AI agents](https://qveris.ai/guides/market-data-api-for-ai-agents/)
- [AI stock research agent](https://qveris.ai/guides/ai-stock-research-agent/)
- [Best Free Stock APIs](https://qveris.ai/guides/stock-api-free-comparison/)
