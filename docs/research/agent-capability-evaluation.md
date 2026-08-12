# Agent Capability Evaluation

Status key: `read` means the paper was read for this index. `candidate` means
the citation was discovered and is awaiting a full reading. All entries are
external design research, not benchmark evidence.

## Read

| Paper | Focus | Relevance to this repository | Boundary |
| --- | --- | --- | --- |
| Mittal (2026), [*Capability Advertisement as a Market for Lemons*](https://arxiv.org/abs/2606.03034) — arXiv:2606.03034 | Capability claims as asymmetric information; descriptors, screening, and reputation | Supports keeping measured CAP facts, evidence provenance, extractor version, suite fingerprint, and freshness visible instead of trusting provider descriptions. | Its Trust Layer is a proposal, not evidence that a Provider or Access Path is reliable. It does not justify an aggregate provider or Agent-friendly score. |
| Liu et al. (2023), [*AgentBench: Evaluating LLMs as Agents*](https://arxiv.org/abs/2308.03688) — arXiv:2308.03688 | Multi-environment evaluation of LLM reasoning and decision-making as agents | Reinforces evaluating observable task outcomes in an environment rather than inferring capability from a model or tool description. | Its benchmark is an external source; its task text cannot be copied into a CAP without question-bank provenance and a CAP-owned measurement contract. |
| Qin et al. (2023), [*ToolLLM: Facilitating Large Language Models to Master 16000+ Real-world APIs*](https://arxiv.org/abs/2307.16789) — arXiv:2307.16789 | Tool-use data, tool selection, multi-tool execution, and ToolBench/ToolEval | Useful background for the distinction between API invocation mechanics and task-level tool-use success. | This platform's constrained Agent Trial intentionally uses one suite-frozen canonical tool; ToolBench does not relax that product boundary. |
| Guo et al. (2025), [*MCP-AgentBench: Evaluating Real-World Language Agent Performance with MCP-Mediated Tools*](https://arxiv.org/abs/2509.09734) — arXiv:2509.09734 | Outcome-oriented evaluation of agents using MCP-mediated tools | Directly relevant to the MCP execution path and to judging real task completion, rather than interface schema validity alone. | It evaluates an Agent-plus-MCP environment. It must not be used to merge Native and QVeris Access Path results or to infer Provider reliability. |

## Candidates for the next reading pass

- *CAR-bench*: calibration, refusal, and `confident-wrong` observations.
  Discovered through QVeris Academic search on 2026-08-12.
- *General AgentBench* (arXiv:2602.18998): verification gap in multi-skill and
  multi-tool agents. Discovered through QVeris Semantic Scholar search on
  2026-08-12.
- *UProp* (arXiv:2506.17419): delegation-chain reliability and correlated-error
  assumptions. Discovered through QVeris Semantic Scholar search on 2026-08-12.

## Discovery record

On 2026-08-12, the initial search used QVeris CLI's QVeris Academic and Semantic
Scholar capabilities with queries for LLM-agent capability evaluation, tool use,
MCP-mediated evaluation, and AgentBench. The confirmed results above are retained
as stable arXiv references; raw tool responses are intentionally not committed.
