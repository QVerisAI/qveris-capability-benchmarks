from __future__ import annotations

from typing import Any

from pydantic import Field, model_validator

from qveris_bench.models.base import FrozenModel, SemanticVersion, StableId
from qveris_bench.models.enums import RunMode


class BenchmarkCase(FrozenModel):
    case_id: StableId
    cap_id: StableId
    question: str = Field(min_length=1)
    input: dict[str, Any]
    negative_control: bool = False
    expected_observations: tuple[str, ...] = Field(min_length=1)
    completion_conditions: tuple[str, ...] = Field(min_length=1)
    disclosure_limits: tuple[str, ...] = ()
    applicable_provider_ids: tuple[StableId, ...] = ()


class AgentProtocol(FrozenModel):
    model: str = Field(min_length=1)
    prompt_version: SemanticVersion
    canonical_tool: StableId
    maximum_calls: int = Field(ge=1)
    token_budget: int = Field(ge=1)
    timeout_seconds: float = Field(gt=0)


class BenchmarkSuite(FrozenModel):
    suite_id: StableId
    version: SemanticVersion
    cap_id: StableId
    cap_version: SemanticVersion
    case_ids: tuple[StableId, ...] = Field(min_length=1)
    access_path_ids: tuple[StableId, ...] = Field(min_length=1)
    modes: tuple[RunMode, ...] = Field(min_length=1)
    rounds: int = Field(ge=1)
    environment: dict[str, str] = Field(default_factory=dict)
    agent_protocol: AgentProtocol | None = None

    @model_validator(mode="after")
    def require_agent_protocol(self) -> BenchmarkSuite:
        if RunMode.AGENT_TRIAL in self.modes and self.agent_protocol is None:
            raise ValueError("agent_trial mode requires agent_protocol")
        return self
