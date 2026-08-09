# AI 友好度评测协议 v2

**Status:** Contract
**Date:** 2026-08-09

## 1. 定位：AI 友好度是"模型 × 工具契约"协作系统属性

AI 友好度不是模型单方成绩，也不是工具单方质量，而是模型调用该工具完成真实
任务时的协作适配度。协议 v2 把"AI 能不能自己把活干成"拆成四个可测量环节：

| 环节 | 算子 | 测什么 |
|---|---|---|
| 一次调用 | `agent_param_fill` | 读任务 → 填对参数（必填、类型、语义、无幻觉） |
| 错误自愈 | `agent_error_recovery` | 读懂失败响应 → 修正参数 → 重试同一工具成功 |
| 出参解读 | `agent_response_interpretation` | 读出答案（数值/币对/时间），不编造，空态报"无数据" |
| 契约信号 | 失败模式聚合 | 从失败归因反推工具契约的可读性缺陷 |

四个环节各自输出可追溯的通过/失败与失败原因，**不合成 Agent-friendly 综合评分**。

## 2. 一次调用：失败模式归因

`agent_param_fill` 的每次失败必须归因到 8 类失败模式之一，用于指导契约改进：

| 模式 | 含义 | 常见契约诱因 |
|---|---|---|
| `no_tool_call` | 模型没有发起调用 | 描述与任务不匹配 |
| `multiple_tools` | 一次发起多个工具调用 | 契约边界不清晰 |
| `wrong_tool` | 调用其他工具 | 命名/描述歧义 |
| `malformed_arguments` | 参数 JSON 损坏 | 契约字段过于复杂 |
| `missing_required` | 漏必填参数 | 必填字段过多/含义不明 |
| `type_invalid` | 参数类型错误 | 类型枚举未声明 |
| `forbidden_param` | 幻觉多余参数 | 描述引入无关字段 |
| `semantics_mismatch` | 填了但语义不对 | 代码方言、枚举值、格式要求 |

## 3. 错误自愈：一次调用的下一环

`agent_error_recovery` 冻结真实失败响应（供应商返回的错误或空态），要求模型：
先说明失败原因，再用**同一个工具**以修正后的参数重试。

判定（硬门槛）：

- `single_tool`：只调用目标工具；
- `retry_params_correct`：重试参数与契约要求的修正值语义一致；
- `no_forbidden`：未幻觉多余参数。

`error_identified`（是否在文本里点明失败原因）作为诊断子项上报，不作为硬门槛，
避免对模型表达方式做过苛要求。

## 4. 出参解读：空态与占位符

`agent_response_interpretation` 除提取正确性、无幻觉、单位语义外，要求负向/空态
响应不得被当成有效数值：响应中的 `NA`、`null`、空数组、错误消息都属于"无数据"，
模型把占位符报成数值（包括整数 `0`）即判定失败。紧邻 `code/status/错误码/HTTP`
的数字视为引用响应中的错误码（如 `code 400`），不计为编造数值——错误码引用是
正确行为，不因出现数字而误判。

## 5. 难度分层

每个用例声明 `difficulty`，按契约认知负担分层统计，避免把简单用例和方言用例混算：

| 层级 | 定义 | 示例 |
|---|---|---|
| L1 | 单一必填参数 | `symbol=EUR/USD` |
| L2 | 多必填参数 + 枚举约束 | `function` + `from_currency` + `to_currency` |
| L3 | 代码方言/枚举方言 | EODHD `EURUSD.FOREX`、iFinD `USDCNY.FX` |
| L4 | 组合参数（one_of 等） | 预留：split base/quote、隐式时间窗口 |

## 6. 证据与呈现

- 每次运行写 `evidence/private/agent-error-recovery.jsonl`（私有）；`param_fill` 记录
  追加 `failure_mode` 与 `difficulty`。
- 公开文章呈现：各环节通过率 + 失败模式画像 + 可行动的契约改进建议（例如"period
  枚举是 AI 高频踩坑点"），不暴露工具 ID 与 CAP ID，不合成总分。
- 失败模式画像同时是我们向 Harbor 提交契约改进 issue 的输入（先例：#1368–#1371）。
