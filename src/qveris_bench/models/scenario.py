from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from qveris_bench.models.base import FrozenModel, SemanticVersion, StableId

QuestionRole = Literal[
    "core_positive",
    "boundary_negative",
    "coverage",
    "freshness_precision",
    "shape_completeness",
    "agent_contract",
]


class ScenarioRef(FrozenModel):
    scenario_id: StableId
    version: SemanticVersion


class ScenarioCapabilityRequirement(FrozenModel):
    cap_id: StableId
    priority: Literal["p0", "p1", "p2"]
    minimum_question_roles: tuple[QuestionRole, ...] = Field(min_length=1)


class ScenarioCompletionPolicy(FrozenModel):
    required_priorities: tuple[Literal["p0", "p1", "p2"], ...] = Field(min_length=1)
    required_release_state: Literal["verified"]
    missing_dimension_state: Literal["evidence_insufficient"]


class DeveloperScenario(FrozenModel):
    scenario_id: StableId
    version: SemanticVersion
    name: str = Field(min_length=1)
    developer_decision: str = Field(min_length=10)
    target_users: tuple[str, ...] = Field(min_length=1)
    markets: tuple[str, ...] = Field(min_length=1)
    languages: tuple[str, ...] = Field(min_length=1)
    required_capabilities: tuple[ScenarioCapabilityRequirement, ...] = Field(
        min_length=1
    )
    completion_policy: ScenarioCompletionPolicy
    source_ids: tuple[StableId, ...] = Field(min_length=1)
    review_status: Literal["approved"]

    @model_validator(mode="after")
    def reject_duplicate_capability_requirements(self) -> DeveloperScenario:
        cap_ids = [
            str(requirement.cap_id) for requirement in self.required_capabilities
        ]
        if len(cap_ids) != len(set(cap_ids)):
            raise ValueError("scenario contains a duplicate capability requirement")
        for requirement in self.required_capabilities:
            roles = list(map(str, requirement.minimum_question_roles))
            if len(roles) != len(set(roles)):
                raise ValueError("scenario contains duplicate minimum question roles")
        priorities = list(map(str, self.completion_policy.required_priorities))
        if len(priorities) != len(set(priorities)):
            raise ValueError("scenario contains duplicate required priorities")
        return self
