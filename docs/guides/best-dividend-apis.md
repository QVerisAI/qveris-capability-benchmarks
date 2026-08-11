# 2026 分红数据 API 对比：6 家分红与除权数据源实测

## 快速结论

- **A 股分红与送转，直接接同花顺 iFinD 或恒生聚源**（单次成功调用 1.0 credits，Direct Test 4/4，AI 入参 2/2 全对）。两家的差距在失败自愈和响应自解释——工具报错/空数据时 AI 修正重试没通过，Agent 集成需要兜底。
- **全球分红历史，Twelve Data 与 Massive AI 双向最友好**（落参/自愈/自解释全过），Twelve Data 延迟最低（0.4s）、Massive 最便宜（1.0 credits）。Alpha Vantage 延迟 0.6s、EODHD 覆盖最广但 CSV 响应不自解释。
- **选型原则**：按"除息日 + 每股金额 + 币种字段是否完整、AI 是否一次调对"选。数据接口的差异在 AI 自动调用时被放大——字段缺一个，Agent 就多一次猜。

> 本文结论来自本平台 2026-08-10 真实调用实测（Direct Test 2 轮 + AI 友好度四维度，固定模型）。**我们公布证据，不公布排名**——不合成综合评分，每个维度独立呈现。完整方法论见[我们的方法论](_shared/benchmark-methodology.md)。

## 哪个分红 API 能让 AI 自动取到除息日？

这是接分红数据最该问的问题——因为**接口好不好用，在 AI 自动调用时才会暴露**。看结论卡：

| 你的场景 | 首选 | 为什么 | 注意 |
|---|---|---|---|
| A 股分红与送转 | 同花顺 iFinD | Direct Test 4/4，AI 入参 2/2，字段全 | 失败自愈 0/2、币种隐含，需兜底 |
| A 股（机构/合规） | 恒生聚源 | Direct Test 4/4，AI 入参 2/2 | 失败自愈 0/2、响应不自解释 |
| 全球分红历史 | Twelve Data | AI 四维度全过，延迟最低 0.4s | 单次 2.37 credits |
| 低成本批量（美股） | Massive | 单次 1.0 credits 最低，AI 四维度全过 | 延迟 0.8s |
| 覆盖最广（全球） | EODHD | 15 个市场，单连接器多资产 | 单次 2.81 最贵，CSV 不自解释 |
| 延迟/成本均衡（美股） | Alpha Vantage | Direct Test 4/4，AI 落参/自愈通过 | 响应缺币种字段 |

## 6 家分红数据 API 对比总表

2026-08-10 经 QVeris 网关真实执行，固定用例（正向分红检索 + 无效代码负向控制）每单元 2 轮。同一法律实体只占一行（Massive 与 Polygon.io 同源合并，恒生聚源 REST 与 MCP 同源合并）。单次费用为成功调用价，负向控制不计费。

| 供应商 | 实测延迟 | 单次费用 | Direct Test | AI 落参 | AI 自愈 | 自解释 | 市场侧重 |
|---|---|---|---|---|---|---|---|
| 同花顺 iFinD | 0.4s | 1.00 | 合格 | 2/2 | 0/2 | 3/6 | A 股 |
| 恒生聚源 | 0.5s | 1.00 | 合格 | 2/2 | 0/2 | 2/6 | A 股 |
| Twelve Data | 0.4s | 2.37 | 合格 | 2/2 | 2/2 | 6/6 | 全球 |
| Massive | 0.8s | 1.00 | 合格 | 2/2 | 2/2 | 6/6 | 美股 |
| Alpha Vantage | 0.6s | 2.00 | 合格 | 2/2 | 2/2 | 3/6 | 美股/全球 |
| EODHD | 0.8s | 2.81 | 合格 | 2/2 | 0/2 | 2/6 | 全球 |

（AI 落参/自愈 = 通过轮数/2；自解释 = 仅凭响应能确定的字段数/6，测试日期 2026-08-10。自愈 0/2 的 EODHD 为错误信号模糊导致过度修正，A 股两家为漏 `.SH` 后缀。）

![分红数据 API 延迟与单次费用](capability-seo/best-dividend-apis/charts/chart-latency-cost.png)

综合判断：**A 股选同花顺 iFinD 或恒生聚源（AI 入参全对，但失败自愈需兜底）；全球选 Twelve Data（AI 最省心、延迟最低）；低成本选 Massive（最便宜且 AI 全过）。** EODHD 适合"一个连接器全包"的场景，但错误信号模糊、CSV 不自解释，AI 集成成本最高。

## 按使用场景选择

### A 股分红与送转：同花顺 iFinD、恒生聚源

两家都通过 Direct Test 4/4、AI 入参 2/2，单次成功调用 1.0 credits。**同花顺 iFinD 字段更全**（每股派现、送转比例、公告日期），**恒生聚源适合机构/合规**。但两者失败自愈都是 0/2：工具报错或返回空数据后，AI 修正重试没通过（漏交易所后缀 `.SH`）。**Agent 自动调用这两家，需要自己处理失败重试**——单次调用没问题，出错后的自愈是短板。

### 全球分红历史：Twelve Data、Alpha Vantage、EODHD、Massive

- **Twelve Data**：AI 四维度全过，延迟最低（0.4s），响应自带币种——Agent 自动调用最省心的海外选项
- **Massive**：单次最便宜（1.0 credits）且 AI 四维度全过，响应结构清晰（`cash_amount` + `currency`）
- **Alpha Vantage**：Direct Test 4/4、AI 落参/自愈通过；响应缺币种字段（自解释 3/6），仅凭响应 AI 需假定美元
- **EODHD**：覆盖最广（15 市场）；但错误信号模糊（`Symbol not found` 无格式提示）导致失败自愈 0/2，CSV 响应不自解释，AI 集成成本最高

### 低成本批量查询

Massive、同花顺 iFinD、恒生聚源均单次 1.0 credits。海外批量选 Massive，A 股批量选同花顺 iFinD 或恒生聚源。

## 供应商深度解析

**同花顺 iFinD —— A 股字段最全，AI 入参正确，失败自愈需兜底**：官方站点：[iFinD 量化数据 API](https://quantapi.51ifind.com/)。实测延迟 0.4s、单次成功调用 1.0 credits、Direct Test 4/4，返回每股派现（贵州茅台 2025 年度每股 28.02 元）与送转比例。AI 入参 2/2、失败自愈 0/2（重试漏 `.SH` 后缀）；响应自解释 3/6（除息日与币种无法仅凭响应确定）。

**恒生聚源 —— A 股数据完整，AI 入参正确，响应不自解释**：官方产品页见[聚源基础数据库](https://www.gildata.com/products/core-data.html)。实测延迟 0.5s、单次成功调用 1.0 credits、Direct Test 4/4。AI 入参 2/2、失败自愈 0/2（漏 `.SH` 后缀）；响应自解释 2/6（除息日、币种均无法仅凭响应确定）。

**Twelve Data —— 响应结构清晰，AI 双向友好**：官方文档：[Twelve Data API](https://twelvedata.com/docs)。实测延迟 0.4s（最低）、单次 2.37 credits、Direct Test 4/4；AI 落参 2/2、失败自愈 2/2、出参解读 4/4、响应自解释 6/6，是目前 AI 双向最友好的海外选项。

**Massive —— 最便宜，AI 四维度全过**：官方网站：[Massive](https://massive.io/)。实测延迟 0.8s、单次成功调用 1.0 credits、Direct Test 4/4；AI 落参 2/2、失败自愈 2/2、响应自解释 6/6。适合低频分红查询与历史回溯。

**Alpha Vantage —— 延迟低，AI 落参/自愈通过**：官方文档：[Alpha Vantage 文档](https://www.alphavantage.co/documentation/)。实测延迟 0.6s、单次成功调用 2.0 credits、Direct Test 4/4；AI 落参 2/2、失败自愈 2/2、响应自解释 3/6（`data` 数组缺币种字段）。

**EODHD —— 全球覆盖，错误信号模糊，CSV 不自解释**：官方文档：[EODHD 金融 API](https://eodhd.com/financial-apis/)。实测延迟 0.8s、单次成功调用 2.81 credits（最高）、Direct Test 4/4；AI 落参 2/2、失败自愈 0/2（错误信号 `Symbol not found` 无格式提示，模型过度修正加 `.US` 后缀）、响应自解释 2/6（CSV 响应缺字段语义与币种）。Agent 自动调用需补字段映射。

### AI 友好度维度明细

**入参（AI 能否按契约填对参数，2 轮）——6 家全部通过**

| 供应商 | 通过率 | 实测说明 |
|---|---|---|
| EODHD | 2/2 | `symbol=AAPL` 正确 |
| Twelve Data | 2/2 | `symbol=AAPL` 正确 |
| Massive | 2/2 | `ticker=AAPL` 正确 |
| Alpha Vantage | 2/2 | `function=DIVIDENDS, symbol=AAPL` 正确 |
| 恒生聚源 | 2/2 | `stockObject=600519` 正确 |
| 同花顺 iFinD | 2/2 | `codes=600519` 正确 |

**失败自愈（报错后能否修正重试，2 轮）**

| 供应商 | 通过率 | 失败样本 | 失败根因 |
|---|---|---|---|
| Twelve Data | 2/2 | 404 + 文档链接 | 识别 `**symbol** invalid`，重试 `symbol=AAPL` |
| Massive | 2/2 | 200 + 空 `results` | 识别空结果，重试 `ticker=AAPL` |
| Alpha Vantage | 2/2 | 200 + 空 `data` | 识别空数据，重试 `function=DIVIDENDS, symbol=AAPL` |
| EODHD | 0/2 | `Symbol not found` | 过度修正为 `AAPL.US`（契约不要求交易所后缀） |
| 恒生聚源 | 0/2 | 200 + `code:500` | 重试漏 `.SH` 后缀 |
| 同花顺 iFinD | 0/2 | 空数组 `[]` | 重试漏 `.SH` 后缀 |

失败分两类：**EODHD 是错误信号模糊**（只有 `Symbol not found`，没说期望格式，模型画蛇添足加 `.US`）；**A 股两家是代码方言**（重试时漏 `.SH` 后缀）。注意入参探针显示 A 股代码能填对（裸代码可接受），但失败重试时模型倾向补/漏后缀，Agent 需要明确的重试策略。

**响应自解释（仅凭响应能否确定除息日/金额/币种，2 轮）**

| 供应商 | 除息日 | 每股金额 | 币种 | 可确定/6 |
|---|---|---|---|---|
| Twelve Data | 能 | 能 | 能 | 6/6 |
| Massive | 能 | 能 | 能 | 6/6 |
| 同花顺 iFinD | 不能 | 能 | 波动 | 3/6 |
| Alpha Vantage | 能 | 波动 | 不能 | 3/6 |
| EODHD | 波动 | 波动 | 不能 | 2/6 |
| 恒生聚源 | 不能 | 能 | 不能 | 2/6 |

解读：**Twelve Data 与 Massive 响应自带语义**（12D 有 `meta.currency`、Massive 有 `cash_amount` + `currency`）；**Alpha Vantage、EODHD、恒生聚源缺显式币种字段**（AI 只能假定美元/人民币）；**同花顺 iFinD 除息日语义不明确**（`board_announce_date` 是公告日而非除息日）；**EODHD 最差**（CSV 格式 `Date,Dividends` 没有字段名说明，AI 不确定 `Date` 是除息日还是登记日）。

**出参解读**：以 Twelve Data 真实分红响应为冻结样本，AI 正确读出最近一次每股分红 0.27 美元、除息日 2026-05-11（2/2）；负向样本（无效代码返回空列表）正确报告"无分红记录"（2/2）。

### 可下钻的观测记录

**观测卡 1（同花顺 iFinD · A 股代码方言 · 失败自愈 0/2）**：失败响应 `[]` → AI 识别"无数据"后重试 `{"codes": "600519"}` 或补后缀，判定未过。A 股代码方言（`600519` vs `600519.SH`）在失败重试时是模型的坑——入参能填对，但出错后的修正不稳定。

**观测卡 2（EODHD · 错误信号模糊 · 失败自愈 0/2）**：失败响应 `Symbol not found`（无格式提示）→ AI 改成 `AAPL.US`，但契约实际接受裸 `AAPL` → 判定未过。错误信号若带上格式提示（如"请使用 AAPL 或 AAPL.US"），这类过度修正可避免。

**观测卡 3（EODHD · CSV 响应 · 自解释 2/6）**：冻结响应 `Date,Dividends\n2024-02-09,0.24\n...` → AI 无法稳定确定 `Date` 是除息日还是其他日期、`Dividends` 的每股口径、以及币种。CSV 只有列名没有字段语义，Agent 集成需外部文档补字段映射。

## 分红 API 的真实限制

接口都返回数据，但**这些坑会在生产环境咬你**：

1. **除息日 vs 登记日 vs 支付日口径混乱**：不同接口对 `Date` 的定义不同——同花顺 iFinD 的 `board_announce_date` 是公告日、EODHD 的 CSV `Date` 是除息日还是登记日 AI 无法确定。**接之前必须确认口径**。
2. **金额口径（每股 vs 每 10 股）**：A 股接口常返回"每 10 股派 280 元"（iFinD `plan_description` 写"每 10 股派 280.2423 元"）但字段是每股——AI 只看字段名会把金额当每股用，**差 10 倍**。
3. **币种隐含**：恒生聚源、同花顺 iFinD、Alpha Vantage、EODHD 的响应不显式带币种——AI 只能假定。
4. **错误信号弱**：EODHD 的 `Symbol not found` 无格式提示，A 股两家对无效代码返回静默空——AI 若不做数据校验，会把空数据当成功结果。
5. **负向控制重要性**：接口对无效代码的行为差异（明确报错 vs 静默空）直接决定 Agent 能否自愈。

## 市场覆盖

覆盖判定以工具 namespace 覆盖为准（claimed_namespaces − SV 探测失败的 unsupported_namespaces，经 SNS 注册表解析）。以下为 claimed 口径，namespace 探测补跑后可能收缩。

| 供应商 | US | CN | HK | JP | UK | DE | FR | ES | CH | NL | SE | NO | BR | CA | TW |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| EODHD | ● | ● | ● | ● | ● | ● | ● | ● | ● | ● | ● | ● | ● | ● | ● |
| Twelve Data | ● | ● | ● | ● | ● | ● | ○ | ○ | ○ | ○ | ○ | ○ | ○ | ○ | ○ |
| Alpha Vantage | ● | ● | ● | ● | ● | ● | ○ | ○ | ○ | ○ | ○ | ○ | ○ | ○ | ○ |
| Massive（原 Polygon.io） | ● | ○ | ○ | ○ | ○ | ○ | ○ | ○ | ○ | ○ | ○ | ○ | ○ | ○ | ○ |
| 恒生聚源 | ○ | ● | ○ | ○ | ○ | ○ | ○ | ○ | ○ | ○ | ○ | ○ | ○ | ○ | ○ |
| 同花顺 iFinD | ○ | ● | ○ | ○ | ○ | ○ | ○ | ○ | ○ | ○ | ○ | ○ | ○ | ○ | ○ |

![分红数据 API 市场覆盖](capability-seo/best-dividend-apis/charts/chart-market-coverage.png)

说明：EODHD 声明覆盖 15 个市场、最广；Twelve Data 与 Alpha Vantage 声明 6 个市场；Massive、恒生聚源、同花顺 iFinD 分别聚焦美股与 A 股。

## 怎么选（决策清单）

1. **先定市场**：A 股（同花顺 iFinD / 恒生聚源）还是全球（Twelve Data / Massive / Alpha Vantage / EODHD）。
2. **确认字段**：除息日、每股派现、送转比例、公告日期、币种——优先字段完整且 AI 自愈达标的。
3. **Agent 自动调用**：优先 AI 落参与自愈均达标的（Twelve Data、Massive、Alpha Vantage）；A 股两家补失败重试兜底；EODHD 补字段映射并留意过度修正。
4. **跑两轮冒烟测试**：用你自己的真实标的跑 2 轮，核对除息日口径和金额单位后再投入生产。

## 分红 API Python 示例（Twelve Data）

```python
import httpx

# Twelve Data 分红接口
resp = httpx.get(
    "https://api.twelvedata.com/dividends",
    params={"symbol": "AAPL", "start_date": "2026-01-01", "end_date": "2026-08-09"},
    headers={"Authorization": "apikey YOUR_KEY"},
)
data = resp.json()
# data = {"meta": {"currency": "USD", ...}, "dividends": [{"ex_date": "2026-05-11", "amount": 0.27}]}
latest = data["dividends"][0]
print(latest["ex_date"], latest["amount"], data["meta"]["currency"])
```

注意：Twelve Data 响应自带 `meta.currency`——接 A 股接口时（如同花顺 iFinD、恒生聚源）必须自己补币种映射，否则金额会被当美元用。

## 常见问题

**本次测试中哪家分红数据 API 最好？** 没有普遍最优：A 股首选同花顺 iFinD 与恒生聚源（AI 入参全对、Direct Test 4/4，但失败自愈需兜底）；全球 Twelve Data 与 Massive AI 友好度最好，Twelve Data 延迟最低、Massive 最便宜。

**哪个最便宜？** Massive、同花顺 iFinD、恒生聚源均单次成功调用 1.0 credits；EODHD 2.81 最贵。

**AI 自动调用选哪家？** 六家 AI 落参 2/2 全对；失败自愈 Twelve Data、Massive、Alpha Vantage 全过，EODHD 与 A 股两家 0/2；响应自解释 Twelve Data 与 Massive 6/6 最好。

**响应自解释性哪家最好？** Twelve Data 与 Massive 6/6（自带币种与字段语义）；Alpha Vantage 与同花顺 iFinD 3/6、EODHD 与恒生聚源 2/6（缺显式币种）。

**这次测试和第三方评估快照有什么关系？** 结论全部来自本平台 Direct Test 与 AI 探针；第三方快照只用于构建候选名单和异常对比，不作为发布依据。

## 局限与时效

- 本文为 2026-08-10 单次执行快照：Direct Test 固定用例 × 2 轮，非全量场景认证；延迟/费用为经 QVeris 网关平均值，不代表供应商直连或 p95，会随套餐、路由与市场状况变化。
- AI 友好度基于固定模型单次测试，模型对同一失败响应的重试参数存在轮间波动（如 EODHD 一轮 `AAPL` 成功、一轮 `AAPL.US` 失败），判定以逐轮真实执行结果为准。
- 响应自解释以各家一个冻结响应为样本；出参解读以 Twelve Data 为通用样本，各家逐测待补齐。
- 市场覆盖为 claimed 口径，MKT.DIVIDENDS 的 namespace 探测部分缺失（EODHD 未跑、Alpha Vantage 探测失败待复核）。
- Financial Modeling Prep 与雅虎财经本轮未测：FMP 无分红事件列表工具、雅虎无独立分红事件接口，均为工具覆盖缺口。

## 在集成前，先验证这 6 家

每个数字背后是可复现的固定用例。想深入核验某家供应商的接口表现，可在 QVeris 中直接检查：

- [在 QVeris 中检查同花顺 iFinD](https://qveris.ai/providers/ths_ifind)
- [在 QVeris 中检查 Twelve Data](https://qveris.ai/providers/twelvedata)

完整方法论、判定规则与冻结样本见 [我们的方法论](_shared/benchmark-methodology.md) 和 [QVeris Capability Benchmarks](https://github.com/QVerisAI/qveris-capability-benchmarks)。本版聚合证据快照（Direct Test 延迟/费用 + AI 四维度判定，含输入 digest）见 [probe-evidence-2026-08-10.json](capability-seo/best-dividend-apis/probe-evidence-2026-08-10.json)。

## 更正与复测

我们只发布可复现的实测结论，并保留全部固定输入用例。若你是供应商并认为某行不准确，请提交带可复现用例的事实更正；入选与排名均不可购买。每次出新版，我们以同一套固定用例重跑，2–4 小时刷新一轮。

相关指南：

- [Market data API for AI agents](https://qveris.ai/guides/market-data-api-for-ai-agents/)
- [AI stock research agent](https://qveris.ai/guides/ai-stock-research-agent/)
- [Best Free Stock APIs](https://qveris.ai/guides/stock-api-free-comparison/)
- [2026 公司行动数据 API 对比](https://github.com/QVerisAI/qveris-capability-benchmarks/pull/74)
