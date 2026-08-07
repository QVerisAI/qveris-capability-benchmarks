from __future__ import annotations

from typing import Literal

from pydantic import Field, HttpUrl

from qveris_bench.models.base import FrozenModel, StableId


class QuestionSource(FrozenModel):
    source_id: StableId
    name: str = Field(min_length=1)
    reference_url: HttpUrl
    authority_tier: Literal["official_api", "external_benchmark"]
    reproduction_policy: Literal["citation_only"]


class CandidateCapability(FrozenModel):
    cap_id: StableId
    name: str = Field(min_length=1)
    lifecycle: Literal["runnable", "candidate"]
    business_use: str = Field(min_length=10)


class BankQuestion(FrozenModel):
    question_id: StableId
    cap_id: StableId
    variant: Literal["positive", "negative"]
    task: str = Field(min_length=1)
    input: dict[str, object]
    required_observations: tuple[str, ...] = Field(min_length=1)
    completion_conditions: tuple[str, ...] = Field(min_length=1)
    source_ids: tuple[StableId, ...] = Field(min_length=1)
    text_origin: Literal["qveris_curated"]
    selection_rationale: str = Field(min_length=10)
    review_status: Literal["approved"]


class QuestionBank(FrozenModel):
    sources: tuple[QuestionSource, ...]
    capabilities: tuple[CandidateCapability, ...]
    questions: tuple[BankQuestion, ...]
