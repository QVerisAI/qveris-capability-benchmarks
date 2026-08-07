from __future__ import annotations

import ipaddress
from typing import Literal

from pydantic import Field, HttpUrl, field_validator, model_validator

from qveris_bench.models.base import FrozenModel, StableId
from qveris_bench.models.scenario import DeveloperScenario, QuestionRole, ScenarioRef


class QuestionSource(FrozenModel):
    source_id: StableId
    name: str = Field(min_length=1)
    reference_url: HttpUrl
    authority_tier: Literal[
        "official_api", "official_market_source", "external_benchmark"
    ]
    reproduction_policy: Literal["citation_only"]
    repository_commit: str | None = Field(default=None, pattern=r"^[a-f0-9]{40}$")
    source_task_ids: tuple[str, ...] = ()

    @field_validator("reference_url")
    @classmethod
    def require_canonical_public_url(cls, value: HttpUrl) -> HttpUrl:
        if (
            value.scheme != "https"
            or not value.host
            or value.username
            or value.password
            or value.query
            or value.fragment
        ):
            raise ValueError("source must use a canonical public HTTPS URL")
        host = (value.host or "").lower()
        try:
            address = ipaddress.ip_address(host)
        except ValueError:
            address = None
        if (
            address is not None
            and not address.is_global
            or host == "localhost"
            or host.endswith((".localhost", ".local", ".internal"))
        ):
            raise ValueError("source must use a public host")
        return value

    @model_validator(mode="after")
    def require_immutable_repository_provenance(self) -> QuestionSource:
        host = self.reference_url.host or ""
        if (
            self.authority_tier == "external_benchmark"
            and host.lower() == "github.com"
            and (not self.repository_commit or not self.source_task_ids)
        ):
            raise ValueError(
                "external benchmark requires immutable repository provenance"
            )
        return self


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
    scenario_refs: tuple[ScenarioRef, ...] = ()
    evaluation_contract: QuestionEvaluationContract | None = None
    text_origin: Literal["qveris_curated"]
    selection_rationale: str = Field(min_length=10)
    review_status: Literal["approved"]


class QuestionBank(FrozenModel):
    sources: tuple[QuestionSource, ...]
    capabilities: tuple[CandidateCapability, ...]
    questions: tuple[BankQuestion, ...]
    scenarios: tuple[DeveloperScenario, ...]
