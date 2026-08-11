# 2026 分红数据 API 对比：6 家分红与除权数据源实测

## 快速结论

- **A 股分红与送转，直接接同花顺 iFinD**（单次 0.50 credits，字段最全含每股派现/送转/公告日），但必须自己加代码规范化——AI 自动调用会把 `600519` 漏成 `600519.SH`，或把 period 填成契约不存在的 `year`。
- **全球分红历史，Twelve Data 最省心**（响应自带 `meta.currency` + `ex_date` + `amount`，AI 落参/自愈/自解释全过），Alpha Vantage 延迟最低（0.6s），Massive 单次最便宜（0.50 credits）。
- **选型原则**：按"除息日 + 每股金额 + 币种字段是否完整、AI 是否一次调对"选，不是按免费或品牌。数据接口的差异在 AI 自动调用时被放大 10 倍——字段缺一个，Agent 就多一次猜。

> 本文结论来自本平台 2026-08-10 真实调用实测（Direct Test 2 轮 + AI 友好度四维度，固定模型）。**我们公布证据，不公布排名**——不合成综合评分，每个维度独立呈现。完整方法论见[我们的方法论](docs/guides/_shared/benchmark-methodology.md)。

## 哪个分红 API 能让 AI 自动取到除息日？

这是接分红数据最该问的问题——因为**接口好不好用，在 AI 自动调用时才会暴露**。看四张结论卡：

| 你的场景 | 首选 | 为什么 | 注意 |
|---|---|---|---|
| A 股分红与送转 | 同花顺 iFinD | 单次 0.50 credits，字段最全 | AI 代码方言是坑，需兜底 |
| A 股（机构/合规） | 恒生聚源 | 单次 0.50 credits，Direct Test 4/4 | AI 落参与自愈均不过 |
| 全球分红历史 | Twelve Data | AI 四维度全过，响应自带币种 | 单次 1.19 credits |
| 低成本批量（美股） | Massive | 单次 0.50 credits，响应结构清晰 | 延迟最高 1.1s |
| 延迟优先（美股） | Alpha Vantage | 实测 0.6s 最低 | 响应缺币种字段 |
| 覆盖最广（全球） | EODHD | 14 个市场，单连接器多资产 | 单次最贵 1.41，CSV 不自解释 |

## 6 家分红数据 API 对比总表

2026-08-10 经 QVeris 网关真实执行，固定用例（AAPL 分红历史检索 + 无效代码负向控制）每单元 2 轮。同一法律实体只占一行（Massive 与 Polygon.io 同源合并，恒生聚源 REST 与 MCP 同源合并）。

| 供应商 | 实测延迟 | 单次费用 | Direct Test | AI 落参 | AI 自愈 | 自解释 | 市场侧重 |
|---|---|---|---|---|---|---|---|
| 同花顺 iFinD | 0.4s | 0.50 | 合格 | 0/2 | 0/2 | 2/6 | A 股 |
| 恒生聚源 | 0.8s | 0.50 | 合格 | 0/2 | 0/2 | 4/6 | A 股 |
| Twelve Data | 0.6s | 1.19 | 合格 | 2/2 | 2/2 | 6/6 | 全球 |
| Alpha Vantage | 0.6s | 1.00 | 合格 | 2/2 | 2/2 | 4/6 | 美股/全球 |
| EODHD | 1.5s | 1.41 | 合格 | 2/2 | 1/2 | 1/6 | 全球 |
| Massive | 1.1s | 0.50 | 合格 | 2/2 | 2/2 | 6/6 | 美股 |

（AI 落参/自愈 = 通过轮数/2；自解释 = 仅凭响应能确定的字段数/6，测试日期 2026-08-10。）

![分红数据 API 延迟与单次费用](capability-seo/best-dividend-apis/charts/chart-latency-cost.png)

综合判断：**A 股选同花顺 iFinD（字段最全）+ 恒生聚源（机构合规），但都要代码兜底；全球选 Twelve Data（AI 最省心）或 Alpha Vantage（延迟最低）；美股批量选 Massive（最便宜）。** EODHD 适合"一个连接器全包"的场景，但 CSV 响应和模糊错误信号让 AI 集成成本最高。

## 按使用场景选择

### A 股分红与送转：同花顺 iFinD、恒生聚源

两家都通过核心用例、单次 0.50 credits。**iFinD 字段更全**（每股派现、送转比例、公告日期），**恒生聚源适合机构/合规**（Direct Test 4/4）。但两者 AI 自动调用都有硬伤：模型始终不用标准代码 `600519.SH`（裸代码或名称），iFinD 还会把 `period` 填成契约不存在的 `year`/`年报`。**接 A 股必须自己做代码规范化 + 枚举校验。**

### 全球分红历史：Twelve Data、Alpha Vantage、EODHD、Massive

- **Twelve Data**：AI 四维度全过，响应自带币种——Agent 自动调用最省心的海外选项
- **Alpha Vantage**：延迟最低（0.6s），AI 落参/自愈通过；响应缺币种，AI 需假定美元
- **EODHD**：覆盖最广（14 市场）；CSV 响应不自解释、错误信号模糊，AI 集成成本最高
- **Massive**：单次最便宜（0.50 credits）但延迟最高（1.1s），响应结构清晰适合低频

### 低成本批量查询

恒生聚源、同花顺 iFinD、Massive 均单次 0.50 credits。海外批量选 Massive，A 股批量选恒生/iFinD。

## 供应商深度解析

**同花顺 iFinD —— A 股字段最全，period 枚举是 AI 陷阱**：官方站点：[iFinD 量化数据 API](https://quantapi.51ifind.com/)。实测延迟 0.4s、单次 0.50 credits、Direct Test 4/4，返回每股派现（贵州茅台 2025 年度每股 28.02 元）与送转比例。AI 落参 0/2、失败自愈 0/2（`codes` 漏 `.SH`、`period` 填 `year`/`年报`）；响应自解释 2/6。

**恒生聚源 —— A 股数据完整，AI 需代码兜底**：官方产品页见[聚源基础数据库](https://www.gildata.com/products/core-data.html)。实测延迟 0.8s、单次 0.50 credits、Direct Test 4/4。AI 落参 0/2、失败自愈 0/2（始终不用 `600519.SH`），响应自解释 4/6（字段全但人民币隐含）。

**Twelve Data —— 响应结构清晰，AI 双向友好**：官方文档：[Twelve Data API](https://twelvedata.com/docs)。实测延迟 0.6s、单次 1.19 credits、Direct Test 4/4；AI 落参 2/2、失败自愈 2/2、出参解读 4/4、响应自解释 6/6，是目前 AI 双向最友好的海外选项。

**Alpha Vantage —— 延迟最低，AI 落参正确**：官方文档：[Alpha Vantage 文档](https://www.alphavantage.co/documentation/)。实测延迟 0.6s（短名单最低）、单次 1.00 credits、Direct Test 4/4；AI 落参 2/2、失败自愈 2/2、响应自解释 4/6（`data` 数组缺币种字段）。

**EODHD —— 全球覆盖，CSV 响应不自解释**：官方文档：[EODHD 金融 API](https://eodhd.com/financial-apis/)。实测延迟 1.5s、单次 1.41 credits（短名单最高）、Direct Test 4/4；AI 落参 2/2、失败自愈 1/2（错误信号模糊导致过度修正）、响应自解释 1/6（CSV 响应缺字段语义与币种）。Agent 自动调用需补字段映射。

**Massive —— 最便宜，响应结构清晰**：官方网站：[Massive](https://massive.io/)。实测延迟 1.1s（短名单最高）、单次 0.50 credits、Direct Test 4/4；AI 落参 2/2、失败自愈 2/2、响应自解释 6/6（`cash_amount` + `currency` 字段齐全）。适合低频分红查询与历史回溯。

### AI 友好度维度明细

**入参（AI 能否按契约填对参数，2 轮）**

| 供应商 | 通过率 | 失败根因 |
|---|---|---|
| EODHD | 2/2 | — |
| Twelve Data | 2/2 | — |
| Massive | 2/2 | — |
| Alpha Vantage | 2/2 | — |
| 恒生聚源 | 0/2 | 未用标准代码 `600519.SH`（一轮裸代码、一轮名称） |
| 同花顺 iFinD | 0/2 | `codes` 漏 `.SH` 后缀；`period` 填成 `year`/`年报`（契约要求 `annual/H1/Q3/Q1`） |

**失败自愈（报错后能否修正重试，2 轮）**

| 供应商 | 通过率 | 失败样本 | 失败根因 |
|---|---|---|---|
| Twelve Data | 2/2 | 404 + 文档链接 | 识别 `**symbol** invalid`，重试 `symbol=AAPL` |
| Massive | 2/2 | 200 + 空 `results` | 识别空结果，重试 `ticker=AAPL` |
| Alpha Vantage | 2/2 | 200 + 空 `data` | 识别空数据，重试 `function=DIVIDENDS, symbol=AAPL` |
| EODHD | 1/2 | `Symbol not found` | 一轮成功；一轮过度修正为 `AAPL.US`（契约不要求交易所后缀） |
| 恒生聚源 | 0/2 | 200 + `code:500` | 重试仍用名称 `贵州茅台` 或裸代码 `600519`，漏 `.SH` |
| 同花顺 iFinD | 0/2 | 空数组 `[]` | 重试 `codes=600519` 漏 `.SH` 后缀 |

失败集中在**同一个根因：A 股代码方言**（`600519` vs `600519.SH`）——入参探针的发现在这里再次出现。EODHD 是另一种失败模式：错误信号太模糊（只有 `Symbol not found`），模型在信息不足时画蛇添足加交易所后缀。

**响应自解释（仅凭响应能否确定除息日/金额/币种，2 轮）**

| 供应商 | 除息日 | 每股金额 | 币种 | 可确定/6 |
|---|---|---|---|---|
| Twelve Data | 能 | 能 | 能 | 6/6 |
| Massive | 能 | 能 | 能 | 6/6 |
| Alpha Vantage | 能 | 能 | 不能 | 4/6 |
| 恒生聚源 | 能 | 能 | 不能 | 4/6 |
| 同花顺 iFinD | 不能 | 能 | 不能 | 2/6 |
| EODHD | 不能 | 波动 | 不能 | 1/6 |

解读：**Twelve Data 与 Massive 响应自带语义**（12D 有 `meta.currency`、Massive 有 `cash_amount` + `currency`）；**Alpha Vantage 与恒生聚源缺显式币种字段**（AI 只能假定美元/人民币）；**同花顺 iFinD 除息日语义不明确**（`board_announce_date` 是公告日而非除息日）；**EODHD 最差**（CSV 格式 `Date,Dividends` 没有字段名说明，AI 不知道 `Date` 是除息日还是登记日）。

### 可下钻的观测记录

**观测卡 1（同花顺 iFinD · A 股代码方言 · 失败自愈 0/2）**：失败响应 `[]` → AI 识别"无数据"后重试 `{"codes": "600519"}`，漏 `.SH` 后缀 → 修正重试 ✗。iFinD 错误信号是静默空，代码方言是模型反复踩的坑。

**观测卡 2（EODHD · 错误信号模糊 · 过度修正）**：失败响应 `Symbol not found`（无格式提示）→ AI 改成 `AAPL.US`，但契约实际接受裸 `AAPL` → 修正重试 ✗。错误信号若带上格式提示（如"请使用 AAPL 或 AAPL.US"），这类过度修正可避免。

**观测卡 3（EODHD · CSV 响应 · 自解释 1/6）**：冻结响应 `Date,Dividends\n2024-02-09,0.24\n...` → AI 无法确定 `Date` 是除息日还是其他日期、`Dividends` 的每股口径、以及币种。CSV 只有列名没有字段语义，Agent 集成需外部文档补字段映射。

## 分红 API 的真实限制

接口都返回数据，但**这些坑会在生产环境咬你**：

1. **除息日 vs 登记日 vs 支付日口径混乱**：不同接口对 `Date` 的定义不同——iFinD 的 `board_announce_date` 是公告日、EODHD 的 CSV `Date` 是除息日还是登记日 AI 无法确定。**接之前必须确认口径**。
2. **金额口径（每股 vs 每 10 股）**：A 股接口常返回"每 10 股派 280 元"（iFinD `plan_description` 写"每 10 股派 280.2423 元"）但字段是每股——AI 只看字段名会把金额当每股用，**差 10 倍**。
3. **币种隐含**：恒生聚源、iFinD 的响应不显式带币种（人民币隐含），Alpha Vantage 缺 currency 字段——AI 只能假定。
4. **错误信号弱**：4 家对无效代码返回静默空（200 + 空数组），不报错不提示——AI 若不做数据校验，会把空数据当成功结果。
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

说明：EODHD 声明覆盖 14 个市场、最广；Twelve Data 与 Alpha Vantage 声明 6 个市场；Massive、恒生聚源、同花顺 iFinD 分别聚焦美股与 A 股。

## 怎么选（决策清单）

1. **先定市场**：A 股（同花顺 iFinD / 恒生聚源）还是全球（Twelve Data / Alpha Vantage / EODHD / Massive）。
2. **确认字段**：除息日、每股派现、送转比例、公告日期、币种——优先字段完整的。
3. **Agent 自动调用**：优先 AI 落参与自愈均达标的（Twelve Data、Massive、Alpha Vantage）；A 股两家补代码规范化 + period 枚举兜底；EODHD 补字段映射并留意过度修正。
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

注意：Twelve Data 响应自带 `meta.currency`——接 A 股接口时（如 iFinD）必须自己补币种映射，否则金额会被当美元用。

## 常见问题

**本次测试中哪家分红数据 API 最好？** 没有普遍最优：A 股首选同花顺 iFinD（字段最全）与恒生聚源（机构合规），但 AI 需代码兜底；全球 Twelve Data 与 Massive AI 友好度最好、Alpha Vantage 延迟最低。

**哪个最便宜？** 恒生聚源、同花顺 iFinD、Massive 均单次 0.50 credits。

**AI 自动调用选哪家？** 海外四家 AI 落参 2/2 全对；失败自愈 Twelve Data、Massive、Alpha Vantage 全过，EODHD 1/2（错误信号模糊）；A 股两家需要代码规范化（`600519.SH`）和 period 枚举兜底。

**响应自解释性哪家最好？** Twelve Data 与 Massive 6/6（自带币种与字段语义）；Alpha Vantage 与恒生聚源 4/6（缺显式币种）；EODHD 1/6 最差（CSV 响应缺字段语义与币种）。

**这次测试和第三方评估快照有什么关系？** 结论全部来自本平台 Direct Test 与 AI 探针；第三方快照只用于构建候选名单和异常对比，不作为发布依据。

## 局限与时效

- 本文为 2026-08-10 单次执行快照：Direct Test 2 个固定用例 × 2 轮，非全量场景认证；延迟/费用为经 QVeris 网关平均值，不代表供应商直连或 p95，会随套餐、路由与市场状况变化。
- AI 友好度基于固定模型单次测试，模型对同一失败响应的重试参数存在轮间波动（如 EODHD 一轮 `AAPL` 成功、一轮 `AAPL.US` 失败）。
- 响应自解释以各家一个冻结响应为样本；出参解读以 Twelve Data 为通用样本，各家逐测待补齐。
- 市场覆盖为 claimed 口径，MKT.DIVIDENDS 的 namespace 探测部分缺失（EODHD 未跑、Alpha Vantage 探测失败待复核）。
- Financial Modeling Prep 与雅虎财经本轮未测：FMP 无分红事件列表工具、雅虎无独立分红事件接口，均为工具覆盖缺口。

## 在集成前，先验证这 6 家

每个数字背后是可复现的固定用例。想深入核验某家供应商的接口表现，可在 QVeris 中直接检查：

- [在 QVeris 中检查同花顺 iFinD](https://qveris.ai/providers/ths_ifind)
- [在 QVeris 中检查 Twelve Data](https://qveris.ai/providers/twelvedata)

完整方法论、判定规则与冻结样本见 [我们的方法论](docs/guides/_shared/benchmark-methodology.md) 和 [QVeris Capability Benchmarks](https://github.com/QVerisAI/qveris-capability-benchmarks)。本版聚合证据快照（Direct Test 延迟/费用 + AI 四维度判定，含输入 digest）见 [probe-evidence-2026-08-10.json](capability-seo/best-dividend-apis/probe-evidence-2026-08-10.json)。

## 更正与复测

我们只发布可复现的实测结论，并保留全部固定输入用例。若你是供应商并认为某行不准确，请提交带可复现用例的事实更正；入选与排名均不可购买。每次出新版，我们以同一套固定用例重跑，2–4 小时刷新一轮。

相关指南：

- [Market data API for AI agents](https://qveris.ai/guides/market-data-api-for-ai-agents/)
- [AI stock research agent](https://qveris.ai/guides/ai-stock-research-agent/)
- [Best Free Stock APIs](https://qveris.ai/guides/stock-api-free-comparison/)
- [2026 公司行动数据 API 对比](https://github.com/QVerisAI/qveris-capability-benchmarks/pull/74)
