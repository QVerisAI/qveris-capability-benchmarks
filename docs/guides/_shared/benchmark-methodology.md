# 我们的方法论

## 我们公布证据，不公布排名

本榜单不回答"哪家供应商最好"——那是一个没有上下文的问题。它只回答一个可验证的问题：**在固定的用例、相同的环境、公开的判定规则下，每一家供应商的接口实际返回了什么。**

我们没有综合评分。一个总分会把"延迟低但自解释差"和"覆盖广但贵"压成一个数字，而那是两件不同的事。每个维度独立呈现，由你按自己产品的优先级裁决。

> **我们不公布排名，我们公布证据。**

---

## 全部结论来自真实调用，公开可复现

本文的每一条数字都来自**本平台真实调用**，不是供应商文档的自述，也不转述任何第三方评分：

- **Direct Test（直连测试）**：对每家供应商的 canonical 工具发起真实调用。每个 CAP 冻结固定用例——**正向用例**（真实标的检索，验证必填字段返回且取值合法）+ **负向控制**（无效输入，验证接口返回空态或明确报错、不编造数据）——每个适用单元执行 2 轮，2 轮稳定才算通过。
- **AI 友好度探针**：让固定模型按真实任务调用工具，测四个环节——**入参**（能否按契约填对参数）、**失败自愈**（报错后能否修正重试）、**出参解读**（能否读出答案、不添油加醋）、**响应自解释**（仅凭响应能否确定数值、单位、币种、时间）。

所有固定用例、判定规则、冻结样本公开在 [QVeris Capability Benchmarks](https://github.com/QVerisAI/qveris-capability-benchmarks) 仓库，可复现。判定规则见 [AI 友好度协议](https://github.com/QVerisAI/qveris-capability-benchmarks/blob/master/docs/ai-friendliness-protocol.md)，证据披露见[证据与披露政策](https://github.com/QVerisAI/qveris-capability-benchmarks/blob/master/docs/evidence-and-disclosure-policy.md)。

---

## 判定规则对标公开标准

我们不发明标准。每一类判定都对照业界公开的规范，让我们的数字可以被任何第三方基准核验：

| 我们的判定 | 对标标准 | 出处 |
|---|---|---|
| 参数正确性（入参 / 失败重试） | 与公开函数调用基准同口径 | [BFCL — Berkeley Function-Calling Leaderboard](https://gorilla.cs.berkeley.edu/leaderboard.html) |
| 货币标识 | ISO 4217 | [ISO 4217 currency codes](https://www.iso.org/iso-4217-currency-codes.html) |
| 时间戳格式 | ISO 8601 | [ISO 8601 date and time format](https://www.iso.org/iso-8601-date-and-time-format.html) |
| 工具调用契约 | MCP / function calling 规范 | [Model Context Protocol](https://modelcontextprotocol.io/) · [Anthropic tool use](https://docs.anthropic.com/en/docs/build-with-claude/tool-use) |
| 负向控制不编造 | 负向测试标准实践 | [ISTQB](https://www.istqb.org/) |
| 响应自解释性 | LLM-friendly API design 实践 | [awesome-agentic-patterns](https://github.com/nibzard/awesome-agentic-patterns/blob/main/patterns/llm-friendly-api-design.md) |

凡响应缺失单位、币种、时区等自解释信息，我们在文章中如实标注，不替供应商补全。

---

## 结果状态与资格

| 状态 | 定义 |
|---|---|
| **合格** | 正向必填字段全部返回且取值合法；负向控制返回空态或明确报错、不编造数据；2 轮结果稳定 |
| **未完全达标** | 任一适用单元未通过上述判定 |
| **未测** | 该供应商无 QVeris canonical 工具或本轮未授权，不计分、不排名 |

第三方评估快照（如 Harbor 覆盖评估）只用于构建候选名单和异常对比，不作为本榜单的发布依据。当我们与第三方评估结论不一致时，以本平台可复现的实测为准。

---

## 更正与复测

我们只发布可复现的实测结论，并保留全部固定输入用例。若你是供应商并认为某行不准确，请提交带可复现用例的事实更正；入选与排名均不可购买。每次出新版，我们以同一套固定用例重跑，2–4 小时刷新一轮。
