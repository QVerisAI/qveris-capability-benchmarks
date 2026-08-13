from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import Field, model_validator

from qveris_bench.models.base import EvidenceRef, FrozenModel, SemanticVersion, StableId
from qveris_bench.models.enums import AccessPathType
from qveris_bench.models.selection import OfficialPricingSnapshot


class StockQuoteCaseResult(FrozenModel):
    case_id: StableId
    role: Literal["positive", "negative_control"]
    state: Literal["passed", "provider_negative"]
    passed_rounds: int = Field(ge=0)
    total_rounds: int = Field(ge=1)
    failure_reasons: tuple[str, ...] = ()
    evidence_refs: tuple[EvidenceRef, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_result(self) -> StockQuoteCaseResult:
        if len(self.evidence_refs) != self.total_rounds:
            raise ValueError("case result requires one public evidence ref per round")
        if self.state == "passed" and (
            self.passed_rounds != self.total_rounds or self.failure_reasons
        ):
            raise ValueError("passed case requires every round and no failure reason")
        if self.state == "provider_negative" and (
            self.passed_rounds != 0 or not self.failure_reasons
        ):
            raise ValueError("provider-negative case requires zero passes and a reason")
        return self


class StockQuoteSelectionRow(FrozenModel):
    provider_id: StableId
    provider_name: str = Field(min_length=1)
    access_path_id: StableId
    access_path_type: AccessPathType
    case_results: tuple[StockQuoteCaseResult, ...] = Field(min_length=1)
    official_pricing: OfficialPricingSnapshot
    qualified: bool

    @model_validator(mode="after")
    def validate_qualification(self) -> StockQuoteSelectionRow:
        positive = [result for result in self.case_results if result.role == "positive"]
        controls = [
            result for result in self.case_results if result.role == "negative_control"
        ]
        expected = bool(positive and controls) and all(
            result.state == "passed" for result in (*positive, *controls)
        )
        if self.qualified != expected:
            raise ValueError(
                "qualified must be derived from all positive and control cases"
            )
        return self


class StockQuoteSelectionSnapshot(FrozenModel):
    snapshot_id: StableId
    version: SemanticVersion
    edition: date
    observation_date: date
    cap_id: Literal["stock-quote"]
    release_digest: EvidenceRef
    suite_fingerprint: str = Field(pattern=r"^[a-f0-9]{64}$")
    github_run_id: str = Field(pattern=r"^[0-9]+$")
    github_sha: str = Field(pattern=r"^[a-f0-9]{40}$")
    input_digests: dict[str, EvidenceRef]
    rows: tuple[StockQuoteSelectionRow, ...] = Field(min_length=1)
    limitations: tuple[str, ...] = ()
