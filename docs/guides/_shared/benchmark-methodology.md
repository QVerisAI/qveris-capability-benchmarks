# 我们的方法论

## 我们公布证据，不公布综合排名

每篇测评只回答一个有边界的问题：在冻结用例、固定 Access Path、公开判定规则和明确的 as-of 时间下，真实接口返回了什么。

Provider 与 Access Path 分开记录。Native API、Native MCP 和 QVeris 是不同的机器接口，即使背后是同一家供应商，也不会合并运行或结果。我们不发布供应商总分、跨 CAP 综合分或全局赢家；开发者应按自己的任务与约束读取各维度事实。

> 我们不公布排名，我们公布可复核的事实。

## Direct Test 是发布门槛

每个适用的 Provider/Access Path 单元都必须真实调用 canonical tool。CAP Pack 负责定义：

- 正向用例需要哪些业务字段、格式、语义和容差；
- 负向控制怎样证明接口会返回空态或明确拒绝，而不是编造记录；
- 哪些市场或用例不适用，以及 N/A 的理由；
- 如何从供应商原始响应提取业务事实。

每个适用用例至少执行 3 轮。基础设施错误不会伪装成供应商失败；供应商侧的空数据或拒绝必须带可核验的失败归因。Direct Test 缺失时，该单元不能进入发布结论。

## 证据先于文章

执行完成后，发布链路先生成 immutable release，再由文章引用 release 事实：

1. 冻结 suite 生成 `run-plan.json` 与唯一 run key；
2. 每个适用单元生成独立终态 cell、outcome 和 evidence ref；
3. 公开证据经过脱敏、披露和来源许可检查；
4. release 绑定 evidence digest、extractor version、suite fingerprint 与 run-plan digest；
5. 离线 replay 重建完全相同的 `release.json` 字节。

原始证据默认私有，API key、个人信息和未经授权的响应不会进入仓库。文章不能用供应商声明补齐 release 没有测得的字段，也不能把 QVeris 网关侧延迟或 credits 写成 Native API 性能或官网价格。

## 状态怎么读

| 文章状态 | 含义 |
|---|---|
| **Qualified** | 该 Access Path 的全部适用正向规则与负向控制在规定轮次内满足发布门槛 |
| **Not qualified** | 至少一个适用单元没有满足 CAP 的公开规则；文章必须写明直接原因 |
| **N/A** | 用例对该 Provider/Access Path 不适用，不计为通过或失败 |
| **Evidence insufficient** | 尚无可发布证据，不从供应商文档、市场常识或其他 Access Path 推断 |

运行层的 `completed`、`provider_negative` 与基础设施失败用于描述单元如何结束，不等同于跨任务评价。Agent-interface 相关观察只有在 CAP 定义了独立测量且 release 携带证据时才展示，并保持参数清晰度、schema 稳定性、错误恢复、分页、语言映射和单工具完成等事实相互独立。

## 更正、复测与供应商参与

历史 release 不原地覆盖。相同规则下的新执行生成新的证明；规则、suite 或结果发生实质变化时生成 successor release。离线 replay 只能证明仓库内文件一致，不能冒充一次新的供应商调用或社区复测。

供应商可以通过 [Provider submission](https://github.com/QVerisAI/qveris-capability-benchmarks/issues/new?template=provider-submission.yml) 提交官方 Access Path，开发者可以提出 [CAP 与方法改进](https://github.com/QVerisAI/qveris-capability-benchmarks/issues/new?template=cap-method-proposal.yml)，任何人都可以用 [Result challenge](https://github.com/QVerisAI/qveris-capability-benchmarks/issues/new?template=result-challenge.yml) 对具体 release 事实提供反证。凭证始终通过私下的安全渠道安排，不能写入 Issue 或 PR。
