# Agent Capability Evaluation

Status key: `read` means the paper was read for this index. `candidate` means
the citation was discovered and is awaiting a full reading. All entries are
external design research, not benchmark evidence.

## Read

| Paper | Focus | Relevance to this repository | Boundary | Checked |
| --- | --- | --- | --- | --- |
| Mittal (2026), [*Capability Advertisement as a Market for Lemons*](https://arxiv.org/abs/2606.03034) — arXiv:2606.03034 | Capability claims as asymmetric information; descriptors, screening, and reputation | Supports keeping measured CAP facts, evidence provenance, extractor version, suite fingerprint, and freshness visible instead of trusting provider descriptions. | Its Trust Layer is a proposal, not evidence that a Provider or Access Path is reliable. It does not justify an aggregate provider or Agent-friendly score. | 2026-08-12 |
| Liu et al. (2023), [*AgentBench: Evaluating LLMs as Agents*](https://arxiv.org/abs/2308.03688) — arXiv:2308.03688 | Multi-environment evaluation of LLM reasoning and decision-making as agents | Reinforces evaluating observable task outcomes in an environment rather than inferring capability from a model or tool description. | Its benchmark is an external source; its task text cannot be copied into a CAP without question-bank provenance and a CAP-owned measurement contract. | 2026-08-12 |
| Qin et al. (2023), [*ToolLLM: Facilitating Large Language Models to Master 16000+ Real-world APIs*](https://arxiv.org/abs/2307.16789) — arXiv:2307.16789 | Tool-use data, tool selection, multi-tool execution, and ToolBench/ToolEval | Useful background for the distinction between API invocation mechanics and task-level tool-use success. | This platform's constrained Agent Trial intentionally uses one suite-frozen canonical tool; ToolBench does not relax that product boundary. | 2026-08-12 |
| Guo et al. (2025), [*MCP-AgentBench: Evaluating Real-World Language Agent Performance with MCP-Mediated Tools*](https://arxiv.org/abs/2509.09734) — arXiv:2509.09734 | Outcome-oriented evaluation of agents using MCP-mediated tools | Directly relevant to the MCP execution path and to judging real task completion, rather than interface schema validity alone. | It evaluates an Agent-plus-MCP environment. It must not be used to merge Native and QVeris Access Path results or to infer Provider reliability. | 2026-08-12 |

## Candidates for the next reading pass

- Kirmayr, Stappen, and Andr'e (2026), [*CAR-bench: Evaluating the Consistency
  and Limit-Awareness of LLM Agents under Real-World Uncertainty*](https://arxiv.org/abs/2601.22027)
  — arXiv:2601.22027. Queue for calibration, refusal, and `confident-wrong`
  observations. Checked 2026-08-12.
- Li et al. (2026), [*Benchmark Test-Time Scaling of General LLM Agents*](https://arxiv.org/abs/2602.18998)
  — arXiv:2602.18998. The paper introduces General AgentBench and may inform
  work on the verification gap in multi-skill and multi-tool agents. Checked
  2026-08-12.
- Duan et al. (2025), [*UProp: Investigating the Uncertainty Propagation of LLMs
  in Multi-Step Agentic Decision-Making*](https://arxiv.org/abs/2506.17419) —
  arXiv:2506.17419. Queue for its multi-step uncertainty-propagation model.
  Checked 2026-08-12.

## Discovery record

On 2026-08-12, the initial search used QVeris CLI's QVeris Academic and Semantic
Scholar capabilities with queries for LLM-agent capability evaluation, tool use,
MCP-mediated evaluation, and AgentBench. The confirmed results above are retained
as stable arXiv references; raw tool responses are intentionally not committed.
