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


class ApplicabilityRule(FrozenModel):
    case_id: StableId
    access_path_id: StableId
    mode: RunMode | None = None
    reason: str = Field(min_length=10)


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
    outcome_rules_file: str = Field(
        default="outcome-rules.yaml", pattern=r"^[a-z0-9][a-z0-9.-]*\.yaml$"
    )
    agent_protocol: AgentProtocol | None = None
    not_applicable: tuple[ApplicabilityRule, ...] = ()

    @model_validator(mode="after")
    def require_agent_protocol(self) -> BenchmarkSuite:
        for field_name, values in (
            ("case_ids", self.case_ids),
            ("access_path_ids", self.access_path_ids),
            ("modes", self.modes),
        ):
            if len(values) != len(set(values)):
                raise ValueError(f"duplicate {field_name}")
        if RunMode.DIRECT not in self.modes:
            raise ValueError("modes must include direct")
        if RunMode.AGENT_TRIAL in self.modes and self.agent_protocol is None:
            raise ValueError("agent_trial mode requires agent_protocol")
        for rule in self.not_applicable:
            if rule.case_id not in self.case_ids:
                raise ValueError(f"not_applicable references {rule.case_id}")
            if rule.access_path_id not in self.access_path_ids:
                raise ValueError(f"not_applicable references {rule.access_path_id}")
            if rule.mode is not None and rule.mode not in self.modes:
                raise ValueError(
                    f"not_applicable references unavailable mode {rule.mode}"
                )
        return self
