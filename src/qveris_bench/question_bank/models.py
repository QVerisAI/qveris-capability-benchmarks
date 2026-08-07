from __future__ import annotations

from typing import Literal

from pydantic import Field, HttpUrl, field_validator

from qveris_bench.models.base import FrozenModel, SemanticVersion, StableId

QuestionRole = Literal[
    "core_positive",
    "boundary_negative",
    "coverage",
    "freshness_precision",
    "shape_completeness",
    "agent_contract",
]


class QuestionSource(FrozenModel):
    source_id: StableId
    name: str = Field(min_length=1)
    reference_url: HttpUrl
    authority_tier: Literal[
        "official_api", "official_market_source", "external_benchmark"
    ]
    reproduction_policy: Literal["citation_only"]

    @field_validator("reference_url")
    @classmethod
    def require_canonical_public_url(cls, value: HttpUrl) -> HttpUrl:
        if (
            value.scheme != "https"
            or value.username
            or value.password
            or value.query
            or value.fragment
        ):
            raise ValueError("source must use a canonical public HTTPS URL")
        return value


class CandidateCapability(FrozenModel):
    cap_id: StableId
    name: str = Field(min_length=1)
    lifecycle: Literal["runnable", "candidate"]
    business_use: str = Field(min_length=10)


class QuestionEvaluationContract(FrozenModel):
    market: str = Field(min_length=1)
    language: str = Field(min_length=1)
    as_of: str = Field(min_length=1)
    reference_source_ids: tuple[StableId, ...] = Field(min_length=1)
    reference_rule: str = Field(min_length=10)
    tolerance_rule: str = Field(min_length=3)
    interface_expectations: tuple[str, ...] = Field(min_length=1)
    selection_implication: str = Field(min_length=10)


class BankQuestion(FrozenModel):
    question_id: StableId
    cap_id: StableId
    role: QuestionRole
    task: str = Field(min_length=1)
    input: dict[str, object]
    required_observations: tuple[str, ...] = Field(min_length=1)
    completion_conditions: tuple[str, ...] = Field(min_length=1)
    source_ids: tuple[StableId, ...] = Field(min_length=1)
    scenario_ids: tuple[StableId, ...] = ()
    evaluation_contract: QuestionEvaluationContract | None = None
    text_origin: Literal["qveris_curated"]
    selection_rationale: str = Field(min_length=10)
    review_status: Literal["approved"]


class ScenarioCapabilityRequirement(FrozenModel):
    cap_id: StableId
    priority: Literal["p0", "p1", "p2"]
    minimum_question_roles: tuple[QuestionRole, ...] = Field(min_length=1)


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
    source_ids: tuple[StableId, ...] = Field(min_length=1)
    review_status: Literal["approved"]


class QuestionBank(FrozenModel):
    sources: tuple[QuestionSource, ...]
    capabilities: tuple[CandidateCapability, ...]
    questions: tuple[BankQuestion, ...]
    scenarios: tuple[DeveloperScenario, ...]
