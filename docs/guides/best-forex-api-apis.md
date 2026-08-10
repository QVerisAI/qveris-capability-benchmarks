# 2026 外汇汇率 API 对比：6 条接入路径的价格与证据状态

快速结论：

- 本版比较 Access Path，不把供应商名称当成测评对象。QVeris Access Path、Native API 与 Native MCP 分行记录，不能互相继承测评结果。
- 六条候选路径目前都缺少符合本仓库 release 规范的完整 Direct Test evidence bundle，因此延迟、QVeris 路径观测费用、参数清晰度、错误恢复和响应自解释均标为“证据不足”。
- 供应商官网价格仍可作为独立事实展示。它描述供应商公开套餐，不等于 QVeris 路径价格，也不能与 QVeris credits 换算。

## 供应商官网价格

下表是 Provider 级价格事实，来源仅限供应商官方页面，核实日期为 2026-08-10。它不声明任何 QVeris Access Path 按该套餐计费。

| 供应商 | 免费层 | 公开付费方案 | 官方来源 |
|---|---|---|---|
| Alpha Vantage | 25 次 API 请求/日 | Premium USD 49.99/月起 | [价格页](https://www.alphavantage.co/premium/) |
| Twelve Data | Basic 8 API credits/分钟、800/日 | Grow USD 29/月起 | [价格页](https://twelvedata.com/pricing) |
| EODHD | 20 次 API 调用/日 | All-in-One USD 99.99/月 | [价格页](https://eodhd.com/pricing) |
| 波兰国家银行 NBP | 公共 API 免费，无 API key | 无付费方案 | [官方 API](https://api.nbp.pl/en.html) |
| 同花顺 iFinD | 新账户 2,000 次试用 | 个人版 CNY 40/月（5,000 次）；企业版 CNY 5,000/月（1,000,000 次） | [价格页](https://mcp.51ifind.com/?syncCookieTimes=1#/pricing) |
| 融聚汇 | 无公开免费 API 层 | 商务询价 | [API 服务](https://www.szfiu.com/custom/detail.php?id=api) |

每项结构化价格事实都保留 `verified_at`、`source_digest`、`extractor_version`、`suite_fingerprint`、披露状态和来源许可状态。只有询价入口而没有公开数字的供应商记为“商务询价”，不会从营销文案推断价格。

## Access Path 测评状态

| 供应商与接入路径 | Direct Test | QVeris 路径观测费用 | Agent 接口观察 | 接入入口 |
|---|---|---|---|---|
| Alpha Vantage · QVeris Access Path | 证据不足 | 不可用 | 证据不足 | [官网](https://www.alphavantage.co/) · [在 QVeris 中试用](https://qveris.ai/providers/alphavantage) |
| Twelve Data · QVeris Access Path | 证据不足 | 不可用 | 证据不足 | [官网](https://twelvedata.com/) · [在 QVeris 中试用](https://qveris.ai/providers/twelvedata) |
| EODHD · QVeris Access Path | 证据不足 | 不可用 | 证据不足 | [官网](https://eodhd.com/) · [在 QVeris 中试用](https://qveris.ai/providers/eodhd) |
| 融聚汇 · QVeris Access Path | 证据不足 | 不可用 | 证据不足 | [官网](https://www.szfiu.com/) · [在 QVeris 中试用](https://qveris.ai/providers/fiu_mcp_server) |
| 波兰国家银行 NBP · Native Access Path | 证据不足 | 不适用 | 证据不足 | [官方 API](https://api.nbp.pl/en.html) |
| 同花顺 iFinD · Native Access Path | 证据不足 | 不适用 | 证据不足 | [Native MCP](https://mcp.51ifind.com/) |

旧版文章曾展示部分网关观测数字，但没有为每条事实保留完整 evidence ref、extractor version、suite fingerprint、run key 与 outcome identity。本版不把文章摘要当成底层证据，因此撤回这些数字，等待真实 release bundle 后再恢复。

## 当前能确认什么

### Alpha Vantage、Twelve Data 与 EODHD

三家都公开了外汇数据接口和 Provider 级套餐，QVeris 也有对应候选 Access Path。不过当前仓库没有可验证的 FX release bundle，所以不能比较其延迟、成功率、credits 或 Agent 接口表现。

### 波兰国家银行 NBP

NBP Native API 免费、无需鉴权，官方文档描述兑 PLN 的每日参考汇率。它适合进入后续 Native Direct Test，但官方能力声明不能代替真实执行结果。

### 同花顺 iFinD

iFinD Native MCP 的官方 skill 包能够证明接入方式与套餐。v1.3.0 的公开工具目录没有 FX canonical tool，因此本版不执行受约束 Agent Trial，也不会把旧 QVeris 工具结果改名成 Native MCP 结果。

### 融聚汇

融聚汇公开提供市场数据 API 商务接入入口，QVeris 有港币参考汇率候选路径。官网没有公开价目，且本版缺少完整 release provenance，因此价格记为商务询价，测评指标保持证据不足。

## 后续测试方法

### Direct Test

每条纳入路径必须使用一个固定 canonical tool，执行一个正向用例和一个负向控制，各 2 轮。正向用例检查汇率值与币对标识；负向控制必须返回明确错误或空态，不能编造汇率。任一执行失败或不可用都会让探针非零退出，不能以绿色任务发布。

### Agent 接口观察

Agent Trial 只拿到一个 canonical tool，不做发现、路由或多工具选择。以下观察分别发布，不压缩成单一标签：

- 参数清晰度：必填参数、类型、枚举与工具方言是否容易一次填对。
- 错误恢复：收到错误或空态后，能否解释原因并用同一工具修正重试。
- 响应自解释：仅看响应能否确定币对、数值单位与时间/时区。
- 单工具完成：组合问题能否保持一次 canonical tool 调用。

每条结果必须绑定精确 `(provider_id, access_path_id)`、证据摘要、extractor version、suite fingerprint、run key 与 outcome identity。缺少任一项时保持证据不足。

## 货币覆盖

当前没有符合 release 规范的货币覆盖事实。本版不把旧工具契约或供应商概括性声明画成实测覆盖；下一轮应按货币对逐格执行并绑定证据。

## 局限与时效

- 官网套餐和调用限制可能变化，采购前应重新打开官方价格页核实。
- 未发布的货币对不表示供应商不支持。
- Native 与 QVeris 路径必须分别测试、分别归因，不能共享延迟、费用或 Agent 观察。
- 本文不计算跨路径复合指标或供应商综合排名。

## 常见问题

**为什么没有延迟和 credits 排名？** 当前没有符合 release 规范的底层证据。旧文章数字不能自证，所以本版主动撤回。

**官网月费和 QVeris credits 哪个更便宜？** 不能直接比较。它们属于不同 Access Path、不同计费单位，也没有公开换算关系。

**为什么 NBP 和 iFinD 没有 Native 实测？** NBP 尚未生成冻结 release；iFinD 当前官方 skill 未发布 FX canonical tool。缺少证据时不从供应商声明推断结果。

## 更正与复测

我们只发布带来源和路径身份的事实。若你认为某项记录不准确，请提交官方来源或可复现用例；任何供应商都不能购买入选、结论或排序。
