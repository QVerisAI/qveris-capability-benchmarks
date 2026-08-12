# 2026 年最佳分红数据 API：6 家供应商真实调用、字段差异与 AI Agent 选型指南

如果你的应用必须同时拿到**除权除息日**和**每股现金分红金额**，本次基础实测中，Twelve Data、Alpha Vantage、EODHD 和 Massive 的 QVeris Access Path 连续 3 轮通过字段门槛与无效代码测试。我们又用独立的市场套件覆盖 US、HK、CN、JP、DE、FR、BR、IN、ES：每个适用单元真实调用 2 轮，明确不支持或合同不适用的市场不重复探测。

这不是一张“谁家最好”的综合排行榜，而是一份面向开发者的单能力选型指南。我们回答的是一组连在一起的工程问题：**哪条 Access Path 能返回可信的现金分红事件，调用成本与延迟如何，价格从哪里核验，市场范围又被什么证据证明？**

> **快速建议**：想用一个 QVeris key 接入多家美股数据源，可从本次通过门槛的四条 QVeris Access Path 中选择。跨市场时，EODHD 在 9 个代表市场中通过 7 个，Twelve Data 通过 6 个；Alpha Vantage 的 4 个适用市场全部通过，但另外 5 个已被 QVeris 明确标为不支持。需要响应明确给出 `currency`，优先核验 Twelve Data 和 Massive；已有 iFinD Native MCP 权限，可以复测它的年度累计单位分红字段，但不要把它当成已经绑定日期的单次 Dividend Event。

## 本文目录

- [实测结果一览](#实测结果一览)
- [为什么分红 API 比看起来复杂](#为什么分红-api-比看起来复杂)
- [我们如何测试](#我们如何测试)
- [延迟、credits、价格与市场覆盖](#延迟credits价格与市场覆盖)
- [6 家供应商逐一分析](#6-家供应商逐一分析)
- [不同开发需求怎么选](#不同开发需求怎么选)
- [Agent 接入风险信号](#direct-test-可观察的-agent-接入风险信号)
- [AI Agent 接入时要做的 5 件事](#ai-agent-接入时要做的-5-件事)
- [如何复测与贡献](#如何复测与贡献)
- [限制、披露与更正](#限制披露与更正)
- [常见问题](#常见问题)

## 实测结果一览

基础 Dividend CAP Direct Test 日期为 2026-08-11，包含 A 股或美股正向用例和无效 symbol 负向控制，每条适用 Access Path 各执行 3 轮，共 36 次真实调用。市场覆盖补充测试日期为 2026-08-12：9 个代表市场中共有 27 个适用正向单元，加上 6 条路径的负向控制，各执行 2 轮，共 66 次真实调用。两份 Release 独立计数，不合并成一个通过率。

| 供应商与 Access Path | 本次 CAP 结论 | QVeris gateway 延迟中位数 / 成功调用 credits 中位数 | 官方价格事实 | 9 市场实测 |
|---|---|---:|---|---|
| [恒生聚源](https://www.gildata.com/products/core-data.html)（QVeris）· [Try it in QVeris](https://qveris.ai/providers/hangseng_polysource) | 基础 Release 保持 **Evidence insufficient**；修正身份提取后的市场套件 CN 2/2 | 623 ms / 0.100 credits | 未公开标准价，商务询价 | CN 2/2；其余 8 个 N/A |
| [同花顺 iFinD](https://mcp.51ifind.com/gwstatic/static/ds_web/ifind-mcp-web/skills/SKILL_INSTALL_GUIDE.md)（Native MCP） | **Not qualified**：缺单次事件日期与金额语义 | 不适用，Native MCP 不混入 QVeris 指标 | 个人版 CNY 40/月起，5,000 次请求 | US、HK、CN 均 0/2；其余 6 个 N/A |
| [Twelve Data](https://twelvedata.com/docs#dividends)（QVeris）· [Try it in QVeris](https://qveris.ai/providers/twelvedata) | **Qualified**：核心字段与负向控制 3/3 | 491 ms / 0.237 credits | Grow USD 29/月起；免费层 800 credits/日 | 6/9 通过；HK、CN、ES 0/2 |
| [Alpha Vantage](https://www.alphavantage.co/documentation/#dividends)（QVeris）· [Try it in QVeris](https://qveris.ai/providers/alphavantage) | **Qualified**：核心字段与负向控制 3/3 | 576 ms / 0.200 credits | Premium USD 49.99/月起；免费层 25 次/日 | 4 个适用市场均 2/2；5 个明确 N/A |
| [EODHD](https://eodhd.com/financial-apis/api-splits-dividends/)（QVeris）· [Try it in QVeris](https://qveris.ai/providers/eodhd) | **Qualified**：核心字段与负向控制 3/3 | 779 ms / 0.281 credits | All-in-One USD 99.99/月 | 7/9 通过；JP、IN 0/2 |
| [Massive](https://massive.com/docs/rest/stocks/corporate-actions/dividends)（QVeris）· [Try it in QVeris](https://qveris.ai/providers/massive_stocks) | **Qualified**：核心字段与负向控制 3/3 | 861 ms / 0.100 credits | 当前 registry 价格事实不适用于该 QVeris 路径 | US 2/2；其余 8 个 N/A |

`Qualified` 只表示该 Access Path 在基础 Release 的冻结输入和规则下通过了这一项分红事件能力测试。运行指标、官网套餐和市场实测是独立维度：表中 ms/credits 来自 QVeris gateway 小样本，官网价格是 2026-08-10 核验的供应商声明，市场数字来自另一份可离线 replay 的 Release。任何一项都不能替代持续 SLA、Native API 性能、全量证券覆盖或授权条款。

## 为什么分红 API 比看起来复杂

“查询一只股票的分红”听起来像一个简单接口，但真正写进产品后，开发者通常会碰到五类问题。

### 1. 一个分红事件有不止一个日期

公告日、登记日、除权除息日和支付日回答的是不同问题。收益回测通常依赖除权除息日，现金流预测可能更关心支付日，事件提醒还可能需要公告日。把这些日期混成一个 `date`，程序可以正常运行，却可能在业务上产生错误结论。

本文的最低门槛只要求可核验的 `effective_date` 和 `amount`。其他日期是有价值的附加字段，但不会替代除权除息日。

### 2. 金额不能脱离单位和币种理解

`amount: 0.27` 通常不足以单独支持跨市场计算。开发者还需要确认它是每股现金金额、币种是什么、是否经过拆股调整，以及供应商如何表达特殊股息。本次测试只在响应明确提供币种时发布 `currency`，不会根据交易所或发行人所在地自行补全。

### 3. 同一证券在不同接口里可能有不同 symbol 方言

`AAPL`、`600519.SH` 和供应商内部证券标识可能指向不同的标识体系。一个响应即使带有日期和金额，只要无法证明返回证券就是请求证券，就不能安全进入数据库、回测或 Agent 上下文。基础 Release 因此阻断了恒生聚源旧结果；后续市场套件修正了 `stockcode` 与内部 `stockobject` 的优先级，并用新证据重新验证 CN，但不会改写旧 Release。

### 4. 空结果、无效代码和系统错误不是一回事

“没有分红记录”是合法业务结果；“symbol 不存在”是可归因的负向结果；超时、认证失败或服务异常则是基础设施问题。把三者都转换成空数组，会让上层应用误以为数据完整，只是没有事件。

### 5. Native API 和聚合接入是两种产品选择

Native API 让你直接管理供应商账户、认证和原始协议；QVeris Access Path 用统一 key 降低多供应商接入成本。两种方式都可能有价值，但它们的认证、调用链路和观测延迟不能混为同一结果。因此本文始终把 Provider 与 Access Path 一起写明。

## 我们如何测试

本次测试采用固定用例，而不是让每家供应商挑选最有利的示例。

- **正向用例**：美股路径使用 `AAPL` 和固定历史时间窗；A 股路径使用 `600519.SH` 和同一时间边界。
- **字段门槛**：响应必须提供可核验的除权除息日 `effective_date` 和数值有效的每股现金分红 `amount`。
- **负向控制**：使用明确无效的 symbol，接受空态或可归因的供应商拒绝，不接受编造的分红记录。
- **重复性**：每个适用用例连续执行 3 轮；Direct Test 是强制项。
- **证据处理**：原始响应默认私有，只公开通过脱敏和授权检查的终态事实与 digest。
- **市场补充套件**：固定 US、HK、CN、JP、DE、FR、BR、IN、ES 各一个代表 symbol，每个适用单元执行 2 轮；只有明确不支持或 Access Path 合同不适用才跳过。

实测事实、供应商官方说明和我们的编辑判断使用不同口径：基础结论和市场矩阵分别来自两份 immutable Release；明确 N/A 的来源冻结在 market run plan；产品能力若来自供应商文档，会链接到官方来源；“适合谁”属于基于本次结果的编辑判断，不会伪装成供应商承诺。

## 延迟、credits、价格与市场覆盖

### QVeris 运行表现：可比较，但不能冒充 Native API SLA

[![五条 QVeris 分红 Access Path 的延迟与 credits 取舍](capability-seo/best-dividend-apis/charts/dividend-runtime-tradeoff.png)](capability-seo/best-dividend-apis/charts/dividend-runtime-tradeoff.png)

六条 Access Path 都产生了 6/6 份终态证据，包括 iFind Native MCP；这只能说明固定窗口内没有留下未决运行，不能冒充长期可靠性。图中只放五条 QVeris Access Path：latency 样本为 6 次（3 次正向、3 次负向控制），credits 只统计 3 次成功正向调用。横坐标是 QVeris gateway 延迟中位数，横线显示本次最小—最大值；纵坐标是成功调用 credits 中位数。恒生聚源即使能完成调用，其证券身份仍然被业务语义门禁阻断。

开发者可以用这张图做第一轮工程预算：Twelve Data 在本次样本中延迟中位数最低；恒生聚源和 Massive 的成功调用 credits 中位数最低；EODHD 的观测 credits 与延迟都更高。但样本只有 6 次，不能据此预测峰值、地域差异或生产流量下的 P95/P99。

### 官方价格：能比较入口，不能直接比较总拥有成本

本文将官网套餐与 QVeris credits 分开。前者是供应商公开的套餐事实，后者是这条 QVeris Access Path 的调用观测。套餐包含的产品、频率、交易所授权和再分发权不同，不能只按“每月最低价”排序。

| Provider / Access Path | 免费或试用入口 | 付费入口 | 价格证据作用域 |
|---|---|---|---|
| [恒生聚源 / QVeris](https://www.gildata.com/products/core-data.html) | `Not published for this snapshot.` | `Commercial; see product page.` | 适用于当前 Dividend Access Path |
| [同花顺 iFinD / Native MCP](https://mcp.51ifind.com/?syncCookieTimes=1#/pricing) | `New accounts receive 2,000 trial requests` | `Personal CNY 40/month for 5,000 requests; Enterprise CNY 5,000/month for 1,000,000 requests` | 仅 Native MCP |
| [Twelve Data / QVeris](https://twelvedata.com/pricing) | `Basic with 8 API credits per minute and 800 per day` | `Grow from USD 29/month` | Provider-wide 官方价格 |
| [Alpha Vantage / QVeris](https://www.alphavantage.co/premium/) | `25 API requests per day` | `Premium from USD 49.99/month` | Provider-wide 官方价格 |
| [EODHD / QVeris](https://eodhd.com/pricing) | `20 API calls per day` | `All-in-One USD 99.99/month` | Provider-wide 官方价格 |
| Massive / QVeris | **Evidence insufficient** | **Evidence insufficient** | registry 中的 Stocks 价格未覆盖这条 QVeris Dividend Access Path |

价格会变化，正式采购前应点击各供应商官方链接复核调用额度、实时性、交易所费用、缓存和再分发权限。

### 市场覆盖：只发布可复现的 Dividend Event 实测

[![9 个代表市场、6 条 Access Path 的 Dividend Event 实测矩阵](capability-seo/best-dividend-apis/charts/dividend-market-coverage.png)](capability-seo/best-dividend-apis/charts/dividend-market-coverage.png)

绿色表示固定代表 symbol 连续 2 轮同时返回了可核验的证券身份、`effective_date` 和 `amount`；橙色表示确实调用了 2 轮，但两轮都没有满足同一门槛；灰色 N/A 只用于 QVeris 已明确不支持或 Access Path 合同明确不适用的市场，因此没有重复浪费调用。它不是“未知”，也不是把失败藏起来。

| Provider / Access Path | 2/2 通过的代表市场 | 0/2 已实测未过 | N/A（未重复调用） |
|---|---|---|---|
| 恒生聚源 / QVeris | CN | — | US, HK, JP, DE, FR, BR, IN, ES：合同仅覆盖中国内地交易所 |
| 同花顺 iFinD / Native MCP | — | US, HK, CN：缺单次事件日期与金额 | JP, DE, FR, BR, IN, ES：合同只声明 US/HK/CN |
| Twelve Data / QVeris | US, JP, DE, FR, BR, IN | HK, CN, ES | — |
| Alpha Vantage / QVeris | US, CN, FR, ES | — | HK, JP, DE, BR, IN：QVeris preflight 明确不支持 |
| EODHD / QVeris | US, HK, CN, DE, FR, BR, ES | JP, IN | — |
| Massive / QVeris | US | — | HK, CN, JP, DE, FR, BR, IN, ES：Stocks Access Path 仅适用于美国股票 |

这里的“市场通过”仍然很克制：每个市场只固定了一只代表证券和一个历史窗口，证明的是这条 Provider / Access Path 在该样本上能完成 Dividend Event，不是供应商所有交易所、所有证券、所有历史深度的全球覆盖承诺。需要进入生产时，应把你自己的 symbol、权限、日期范围和再分发条款带入同一套复测。

市场覆盖 Release 共包含 120 个 frozen cells：66 个适用单元都有公开脱敏 terminal，54 个 N/A 单元保留冻结原因。图表只读取这份 Release，不读取不可公开复放的外部快照，也不把供应商宣传补成绿色。

## 6 家供应商逐一分析

### 恒生聚源：CN 新证据已闭环，但旧 Release 不改写

**本次观察**：基础 Release 的提取器误把内部 `stockobject` 当成证券代码，因此按 fail-closed 原则保持 Evidence insufficient。市场补充套件改为优先读取响应 `stockcode`，请求 `600519.SH` 与返回代码完成映射，CN 两轮都满足身份、日期和金额门槛。

**对开发者意味着什么**：字段齐全不等于记录可信，身份映射必须先于业务入库；同时，更正应通过新证据追加发布，不能悄悄改掉历史结果。

**本次建议**：可把恒生聚源列为 A 股复测候选；当前市场套件只有 2 轮，若要升级基础榜单结论，仍应对主 suite 生成一个新的 3 轮 successor release。供应商资料见[聚源基础数据库](https://www.gildata.com/products/core-data.html)，也可查看其 [QVeris Provider 页面](https://qveris.ai/providers/hangseng_polysource)。

### 同花顺 iFinD：只保留 Native MCP，累计分红不能替代单次事件

**本次观察**：同花顺 iFinD（Native MCP）的三轮正向调用都返回了年度累计单位分红字段，但没有提供可核验的除权除息日；无效代码控制为 3/3。

**对开发者意味着什么**：这条路径暴露的是年度累计单位分红值，不能证明它是某次 Dividend Event 的当次金额。如果任务涉及除息日收益、事件日历或价格调整，当前响应不足以完成工作；年度累计值也不能替代事件日期与单次现金金额。

**本次建议**：在本文定义的能力门槛下为 **Not qualified**。本次只评测 [iFinD 官方 Native MCP](https://mcp.51ifind.com/gwstatic/static/ds_web/ifind-mcp-web/skills/SKILL_INSTALL_GUIDE.md)，不把它描述为 QVeris 接入，也不提供 QVeris CTA。

### Twelve Data：核心字段稳定，并明确返回币种

**本次观察**：`AAPL` 正向字段门槛和无效代码控制均为 3/3；样本响应提供 `effective_date`、`amount`、`currency` 和事件数量。

**对开发者意味着什么**：对于需要标准化除权除息日、每股金额和币种的美股工作流，它提供了较直接的数据形状。币种来自响应本身，减少了上层按市场猜测币种的风险。

**本次建议**：适合作为美股分红日历、事件提醒或基础收益分析的候选路径。本文没有测试其全市场覆盖、分页上限或官网套餐限制，选型前仍应查看 [Twelve Data Dividends 文档](https://twelvedata.com/docs#dividends)和 [QVeris Provider 页面](https://qveris.ai/providers/twelvedata)。

### Alpha Vantage：样本中提供更完整的事件时间线

**本次观察**：正向字段门槛与无效代码控制均为 3/3。样本响应除除权除息日和金额外，还提供公告日、登记日和支付日。

**对开发者意味着什么**：如果应用要区分“公司宣布分红”“确定股东资格”和“实际支付”三个阶段，更丰富的日期字段可以减少二次拼接。不过这里只证明这些字段在本次 `AAPL` 样本中出现，不代表所有市场和历史记录都同样完整。

**本次建议**：适合需要多日期事件模型的开发者优先复测。供应商契约见 [Alpha Vantage Dividends 文档](https://www.alphavantage.co/documentation/#dividends)和 [QVeris Provider 页面](https://qveris.ai/providers/alphavantage)。

### EODHD：通过最低字段门槛，数据形状相对精简

**本次观察**：正向字段门槛与无效代码控制均为 3/3；样本公开事实包含除权除息日、金额和事件数量，没有据此推断币种或其他日期。

**对开发者意味着什么**：精简响应适合只需要标准化核心字段的服务，但如果你的业务还依赖公告日、登记日、支付日或币种，应把这些字段加入自己的验收测试，而不是默认存在。

**本次建议**：适合作为核心分红事件查询的候选路径，扩展字段需求需要另行验证。官方说明见 [EODHD Splits and Dividends API](https://eodhd.com/financial-apis/api-splits-dividends/)和 [QVeris Provider 页面](https://qveris.ai/providers/eodhd)。

### Massive：核心字段通过，样本中包含币种和完整日期组

**本次观察**：正向字段门槛与无效代码控制均为 3/3。样本响应提供币种、公告日、登记日、除权除息日和支付日。

**对开发者意味着什么**：这类字段组合适合公司行动流水线和需要明确现金流日期的应用。但不同供应商在固定窗口内返回的事件数量和最新事件并不完全相同，本文没有把“返回了一条有效记录”扩大解释为“历史数据绝对完整”。

**本次建议**：适合优先复测多日期、显式币种的美股工作流。字段说明见 [Massive Dividends 文档](https://massive.com/docs/rest/stocks/corporate-actions/dividends)和 [QVeris Provider 页面](https://qveris.ai/providers/massive_stocks)。

## 不同开发需求怎么选

[![6 条分红数据 Access Path 的 Dividend Event 公开证据热力图](capability-seo/best-dividend-apis/charts/dividend-evidence-heatmap.png)](capability-seo/best-dividend-apis/charts/dividend-evidence-heatmap.png)
<p align="center"><sub>点击查看高分辨率原图；移动端也可直接阅读文中的 HTML 结果表与 Agent 风险信号表</sub></p>

热力图只表示本次固定样本公开了什么证据，不代表供应商在其他市场、symbol 或历史区间的完整能力。“未观察”不能理解成供应商一定没有该字段；“阻断”表示记录存在语义或身份问题，不能直接采信。

### 想用一个 key 快速比较多家供应商

选择 QVeris Access Path。本次通过最低门槛的美股候选包括 Twelve Data、Alpha Vantage、EODHD 和 Massive。统一 key 可以减少认证和调用方式差异，但不会消除供应商之间的字段语义差异。

### 需要公告日、登记日和支付日

优先复测 Alpha Vantage 和 Massive，因为这些字段在本次公开样本中实际出现。不要只看文档字段表；应使用你自己的 symbol、市场和时间范围验证缺失率与历史深度。

### 必须使用响应内的明确币种

优先核验 Twelve Data 和 Massive。本次样本中它们明确提供了 `currency`。其他路径没有提供时，应保持为空或从另一个有明确来源的数据集补充，不能静默猜测。

### 主要处理 A 股分红

恒生聚源在新的 CN 代表样本中已 2/2 通过，可作为 A 股优先复测候选；但基础榜单仍绑定旧的 3 轮 Release，不能用补充套件直接改写为 Qualified。iFinD Native MCP 在 CN 两轮仍缺单次事件日期与金额语义。

### 延迟是第一优先级

先用本文的 QVeris gateway 小样本排出复测顺序，再用你的部署区域、调用频率和目标 symbol 做持续压测。不要把 iFind Native MCP 与 QVeris 路径横比，也不要把 6 次调用的中位数当成生产 SLA。

## Direct Test 可观察的 Agent 接入风险信号

这里没有执行 Agent Trial，也不做跨维度总分。下面只把 Direct Test 已观察到、会影响 Agent 接入的风险逐维度摊开：必需字段能否稳定提取、响应身份能否和请求对应、错误能否被明确归因，以及缺失字段会不会诱导模型自行补全。

| Provider 与 Access Path | 必需事件字段 | 证券身份 | 无效 symbol | 响应内币种 | 附加事件日期 |
|---|---|---|---|---|---|
| 恒生聚源（QVeris） | 基础 Release 被身份门禁阻断；新 CN 样本 2/2 | 新套件已用响应 `stockcode` 映射验证 | 3/3 正确处理 | 未观察到 | 公告日、登记日、支付日 |
| 同花顺 iFinD（Native MCP） | 缺单次金额语义与除权除息日 | 身份一致性未独立测量 | 3/3 正确处理 | 未发布 | 未形成单次事件日期组 |
| Twelve Data（QVeris） | 3/3 | 身份一致性未独立测量 | 3/3 正确处理 | `USD` | 本次仅发布除权除息日 |
| Alpha Vantage（QVeris） | 3/3 | 身份一致性未独立测量 | 3/3 正确处理 | 未观察到 | 公告日、登记日、支付日 |
| EODHD（QVeris） | 3/3 | 身份一致性未独立测量 | 3/3 正确处理 | 未观察到 | 本次仅发布除权除息日 |
| Massive（QVeris） | 3/3 | 身份一致性未独立测量 | 3/3 正确处理 | `USD` | 公告日、登记日、支付日 |

公开事实中的规范化 symbol 可能来自请求输入回填，不能单独证明响应身份一致；只有保留供应商返回标识的来源，并完成 canonical symbol 映射校验，才能把这一维标为通过。参数清晰度、分页和 Agent Trial 在这版 release 中也没有足够证据，因此不按供应商打分。这里的“无效 symbol 3/3”只证明固定负向控制得到了可归因处理，也不等于已经覆盖限流、超时、认证过期和服务端异常等完整错误恢复能力。

## AI Agent 接入时要做的 5 件事

1. **建立规范化事件模型**：至少保留 `symbol`、`effective_date`、`amount`、`currency`、`record_date`、`payment_date`、`declaration_date` 和来源信息；可选字段允许为空。
2. **验证请求与响应身份**：将 canonical symbol 与供应商返回标识进行显式映射和校验。无法证明一致时 fail closed，不让 Agent 猜。
3. **区分空态与失败**：没有事件、无效代码、认证失败、限流和超时必须进入不同状态，避免 Agent 把系统失败解释成“没有分红”。
4. **保留字段来源**：金额、币种和日期都应能追溯到具体 Access Path 与调用证据。多个供应商冲突时，Agent 才能解释差异而不是随意覆盖。
5. **让业务规则独立于供应商响应**：供应商适配层负责认证、调用和原始响应；“什么算一条可用分红事件”由统一规则判断。换供应商时无需重写整个 Agent。

一个足够小、又能保留关键语义的规范化事件可以长这样：

```json
{
  "symbol": "AAPL",
  "effective_date": "2026-05-11",
  "amount": 0.27,
  "currency": "USD",
  "declaration_date": null,
  "record_date": null,
  "payment_date": null,
  "source": {"provider": "example", "access_path": "qveris"}
}
```

这里的 `null` 是诚实的未知值，不是等待 Agent 猜测的空格。请求与响应的 symbol 无法对应，或者 `effective_date`、`amount` 任一缺失时，不应生成一条看似完整的 Dividend Event。

本文不提供笼统的 Agent 综合评分。参数清晰度、schema 稳定性、错误恢复、分页和单工具完成能力应该分别观察；没有相应证据的维度保持 unavailable。

## 如何复测与贡献

### 不需要 key：离线复核公开 release

离线 replay 会验证 run plan、终态 cells、证据 digest、suite fingerprint 和 release 字节是否一致。它不会重新调用供应商，因此证明的是“这份发布物没有被悄悄改写”，不是“供应商今天仍返回相同结果”。

```bash
uv sync --locked --all-groups
uv run qveris-bench release replay releases/dividend-events-2026-q3-v1 \
  --expected-digest sha256:ff44f0d4aa72553949d93910c78af57c29bf46dc39a206aacb97956a081049e0
uv run qveris-bench release replay \
  releases/dividend-events-market-coverage-2026-q3-v1 \
  --expected-digest sha256:52f432c581fc6e8868e9070be21ad1b210b59238fb4c26d252f2a13a2d93f70e
```

你可以检查[基础 release](../../releases/dividend-events-2026-q3-v1/release.json)、[市场覆盖 release](../../releases/dividend-events-market-coverage-2026-q3-v1/release.json)、[Selection Snapshot](capability-seo/best-dividend-apis/selection-snapshot.json)、[基础公开证据](../../evidence/dividend-events-2026-q3-v1/)、[市场公开证据](../../evidence/dividend-events-market-coverage-2026-q3-v1/)和[离线 replay 说明](../release-replay.md)。市场图中的每一个绿色或橙色单元都能沿 `evidence.json` 的 digest 找到对应 terminal。

### 有 key：重新执行真实调用

[Dividend Events live workflow](../../.github/workflows/live-dividend-events-e2e.yml)将基础 binding 分 3 轮执行；[Market coverage workflow](../../.github/workflows/live-dividend-market-coverage-e2e.yml)将 33 个适用 binding 分 2 轮执行：

- 五条 QVeris Access Path 使用 `QVERIS_API_KEY`；
- 同花顺 iFinD 只使用 `IFIND_MCP_API_KEY`，走 Native MCP；
- 凭证通过环境变量或 GitHub Actions secrets 注入，不能写入 fixture、日志或 PR。

新的真实执行不会改写历史 release。输入、规则或结果变化时，应生成 successor release，并保留旧版 digest。

### 供应商与开发者如何参与

供应商可以提交 [Provider submission](https://github.com/QVerisAI/qveris-capability-benchmarks/issues/new?template=provider-submission.yml)，说明 Provider、Access Path、官方接口、授权范围和希望参与的能力。API key 和私有响应不能放进 Issue 或 PR；凭证通过私下的安全渠道处理。

开发者可以贡献 [CAP 与方法提案](https://github.com/QVerisAI/qveris-capability-benchmarks/issues/new?template=cap-method-proposal.yml)，包括边界用例、负向控制、字段规则和可授权来源。认为结果有误时，可以提交带 release digest 与反证的 [Result challenge](https://github.com/QVerisAI/qveris-capability-benchmarks/issues/new?template=result-challenge.yml)。供应商可以更正事实，但不能付费购买纳入、结论或排序。

## 限制、披露与更正

- 本文只测试 Dividend Events 这一项能力，不代表供应商的综合金融数据质量。
- 基础测试只覆盖 `AAPL`、`600519.SH` 和无效 symbol；市场补充套件在 9 个市场各使用一个代表 symbol，不能外推到全量证券。
- 明确 N/A 的市场没有重复调用；判断来源冻结在 market run plan。未知、临时失败或缺少证据不能被改写成 N/A。
- 官网价格来自 2026-08-10 的官方事实快照；没有实测套餐限额、SLA、全市场覆盖、分页、历史修订或企业授权条款。
- QVeris Access Path 的 latency 和 credits 只描述网关侧观测，不能归因于供应商 Native API。
- QVeris 运营平台参与部分 Access Path 的接入，但测试规则、终态证据和复测入口公开；本文不接受付费排名。
- 恒生聚源身份提取修正后的 CN 新证据为 2/2；基础 3 轮 Release 仍保留原结论，升级需发布 successor release。
- 历史 release 不原地修改。成立的更正会通过追加式证明或 successor release 发布。

完整规则见[评测方法论](_shared/benchmark-methodology.md)和 [QVeris Capability Benchmarks](https://github.com/QVerisAI/qveris-capability-benchmarks)。还可以阅读 [Market data API for AI agents](https://qveris.ai/guides/market-data-api-for-ai-agents/)、[AI stock research agent](https://qveris.ai/guides/ai-stock-research-agent/)与 [Best Free Stock APIs](https://qveris.ai/guides/stock-api-free-comparison/)。

## 常见问题

### 哪个分红数据 API 最适合开发者？

没有脱离需求的统一答案。只需要美股除权除息日和每股金额时，本次通过门槛的 Twelve Data、Alpha Vantage、EODHD 和 Massive 都是候选；需要更多事件日期可优先复测 Alpha Vantage 或 Massive；需要明确币种可优先核验 Twelve Data 或 Massive。

### Qualified 是否代表数据绝对完整？

不代表。它只表示固定样本中的必需字段、数值格式和负向控制连续 3 轮通过。完整市场覆盖、所有历史事件和持续 SLA 都需要独立证据。

### 哪家分红 API 在 9 个代表市场中通过最多？

EODHD 通过 7/9，Twelve Data 通过 6/9。Alpha Vantage 的 4 个适用市场全部通过，另外 5 个因 QVeris 明确不支持而记为 N/A；这不能和 7/9、6/9直接当成同分母排名。恒生聚源和 Massive 的合同范围分别只让 CN、US 进入实测，iFind 的 US/HK/CN 都没有满足单次 Dividend Event 门槛。

### 为什么 iFind 返回了年度累计单位分红仍然没有通过？

因为本文测的是“可用于程序处理的分红事件”，最低门槛同时需要单次每股现金金额和可核验的除权除息日。年度累计单位分红既不能证明某次事件的金额，也没有对应事件日期，无法安全支持除息日回测、价格调整或事件提醒。

### 可以直接比较表中的延迟吗？

可以把同一观察窗口、同一 QVeris gateway 边界内的五条路径用于第一轮工程预算和复测排序，但不能把它当成供应商 Native API 性能排名或 SLA。本文也不会把 Native MCP 与 QVeris Access Path 的链路混合比较；正式选型还应补测目标地域与并发下的 P95/P99。

### 我能用自己的 API key 复测吗？

可以。QVeris 已接入的供应商使用一个 `QVERIS_API_KEY`；iFind 使用你自己的 Native MCP key。复测应保留相同输入、规则和轮次，结果变化时创建新的 release，而不是覆盖旧证据。
