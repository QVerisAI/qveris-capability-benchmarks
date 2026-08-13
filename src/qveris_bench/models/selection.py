from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import Field, HttpUrl, model_validator

from qveris_bench.models.base import (
    EvidenceRef,
    FrozenModel,
    SemanticVersion,
    StableId,
)
from qveris_bench.models.enums import AccessPathType

MeasurementState = Literal["measured", "evidence_insufficient", "not_applicable"]
PricingState = Literal["declared", "evidence_insufficient"]
QVerisListPriceState = Literal["declared", "not_applicable"]
MarketResultState = Literal["verified", "provider_negative", "not_applicable"]


class ObservationWindow(FrozenModel):
    start: date
    end: date

    @model_validator(mode="after")
    def validate_order(self) -> ObservationWindow:
        if self.start > self.end:
            raise ValueError("observation window start must not follow end")
        return self


class GatewayMetricsSnapshot(FrozenModel):
    state: MeasurementState
    measurement_boundary: Literal["qveris_gateway"] = "qveris_gateway"
    latency_sample_size: int = Field(ge=0)
    latency_min_ms: float | None = Field(default=None, ge=0)
    latency_median_ms: float | None = Field(default=None, ge=0)
    latency_max_ms: float | None = Field(default=None, ge=0)
    cost_sample_size: int = Field(ge=0)
    median_credits: float | None = Field(default=None, ge=0)
    evidence_refs: tuple[EvidenceRef, ...] = ()
    latency_evidence_refs: tuple[EvidenceRef, ...] = ()
    cost_evidence_refs: tuple[EvidenceRef, ...] = ()

    @model_validator(mode="after")
    def validate_measurement(self) -> GatewayMetricsSnapshot:
        if self.state == "measured":
            latency_values = (
                self.latency_min_ms,
                self.latency_median_ms,
                self.latency_max_ms,
            )
            if (
                self.latency_sample_size == 0
                or len(self.latency_evidence_refs) != self.latency_sample_size
                or any(value is None for value in latency_values)
            ):
                raise ValueError("measured gateway latency requires complete samples")
            complete_latency = tuple(
                value for value in latency_values if value is not None
            )
            if complete_latency != tuple(sorted(complete_latency)):
                raise ValueError(
                    "gateway latency min, median, and max are out of order"
                )
            if self.cost_sample_size != len(self.cost_evidence_refs) or (
                (self.cost_sample_size > 0) != (self.median_credits is not None)
            ):
                raise ValueError("gateway credits require complete samples")
            combined = set(self.latency_evidence_refs) | set(self.cost_evidence_refs)
            if set(self.evidence_refs) != combined:
                raise ValueError("gateway evidence references do not match samples")
        if self.state == "not_applicable" and (
            self.evidence_refs
            or self.latency_evidence_refs
            or self.cost_evidence_refs
            or self.latency_sample_size
            or self.cost_sample_size
            or self.latency_min_ms is not None
            or self.latency_median_ms is not None
            or self.latency_max_ms is not None
            or self.median_credits is not None
        ):
            raise ValueError("not-applicable gateway metrics cannot carry observations")
        if self.state == "evidence_insufficient" and (
            self.evidence_refs
            or self.latency_evidence_refs
            or self.cost_evidence_refs
            or self.latency_sample_size
            or self.cost_sample_size
            or self.latency_min_ms is not None
            or self.latency_median_ms is not None
            or self.latency_max_ms is not None
            or self.median_credits is not None
        ):
            raise ValueError("insufficient gateway metrics cannot carry observations")
        return self


class RunObservationsSnapshot(FrozenModel):
    state: MeasurementState
    terminal_observations: int = Field(ge=0)
    planned_observations: int = Field(ge=0)
    evidence_refs: tuple[EvidenceRef, ...] = ()

    @model_validator(mode="after")
    def validate_measurement(self) -> RunObservationsSnapshot:
        if self.state == "measured" and (
            not self.evidence_refs or self.planned_observations == 0
        ):
            raise ValueError("measured run observations require plan and evidence")
        if self.terminal_observations > self.planned_observations:
            raise ValueError("terminal observations cannot exceed planned observations")
        if self.state == "measured" and (
            len(self.evidence_refs) != self.terminal_observations
        ):
            raise ValueError("run observation evidence must match terminal count")
        if self.state != "measured" and (
            self.terminal_observations
            or self.planned_observations
            or self.evidence_refs
        ):
            raise ValueError("unmeasured run observations cannot carry counts")
        return self


class OfficialPricingSnapshot(FrozenModel):
    state: PricingState
    pricing_id: StableId | None = None
    pricing_url: HttpUrl | None = None
    free_tier: str | None = None
    paid_plans: str | None = None
    verified_at: date | None = None
    source_digest: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    applies_to: str | tuple[StableId, ...] | None = None
    currencies: tuple[str, ...] = ()
    extractor_version: SemanticVersion | None = None
    suite_fingerprint: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    disclosure_level: str | None = None
    license_status: str | None = None

    @model_validator(mode="after")
    def validate_declaration(self) -> OfficialPricingSnapshot:
        required = (
            self.pricing_id,
            self.pricing_url,
            self.free_tier,
            self.paid_plans,
            self.verified_at,
            self.source_digest,
            self.applies_to,
            self.currencies or None,
            self.extractor_version,
            self.suite_fingerprint,
            self.disclosure_level,
            self.license_status,
        )
        if self.state == "declared" and any(item is None for item in required):
            raise ValueError("declared pricing requires complete provenance")
        if self.state == "evidence_insufficient" and any(
            item is not None for item in required
        ):
            raise ValueError("insufficient pricing cannot carry declarations")
        return self


class QVerisListPriceSnapshot(FrozenModel):
    state: QVerisListPriceState
    amount_credits: float | None = Field(default=None, ge=0)
    unit: Literal["per_call"] | None = None
    source: Literal["qveris_inspect"] | None = None
    inspected_at: date | None = None
    snapshot_version: str | None = Field(default=None, min_length=1)
    inspect_response_digest: EvidenceRef | None = None
    extractor_version: SemanticVersion | None = None
    disclosure_level: str | None = None
    license_status: str | None = None
    evidence_ref: EvidenceRef | None = None

    @model_validator(mode="after")
    def validate_price(self) -> QVerisListPriceSnapshot:
        details = (
            self.amount_credits,
            self.unit,
            self.source,
            self.inspected_at,
            self.inspect_response_digest,
            self.extractor_version,
            self.disclosure_level,
            self.license_status,
            self.evidence_ref,
        )
        if self.state == "declared" and any(item is None for item in details):
            raise ValueError("declared QVeris list price requires inspect provenance")
        if self.state == "not_applicable" and any(item is not None for item in details):
            raise ValueError("not-applicable QVeris list price cannot carry facts")
        return self


class SelectionObservation(FrozenModel):
    state: MeasurementState
    passed: int | None = Field(default=None, ge=0)
    total: int | None = Field(default=None, ge=0)
    evidence_refs: tuple[EvidenceRef, ...] = ()

    @model_validator(mode="after")
    def validate_measurement(self) -> SelectionObservation:
        if self.state == "measured" and (
            self.passed is None or self.total is None or not self.evidence_refs
        ):
            raise ValueError(
                "measured selection observation requires counts and evidence"
            )
        if (
            self.passed is not None
            and self.total is not None
            and self.passed > self.total
        ):
            raise ValueError("passed observations cannot exceed total")
        if self.state != "measured" and (
            self.evidence_refs or self.passed is not None or self.total is not None
        ):
            raise ValueError("unmeasured observation cannot carry evidence or counts")
        return self


class AgentInterfaceSnapshot(FrozenModel):
    invalid_input_handling: SelectionObservation
    parameter_clarity: SelectionObservation
    schema_stability: SelectionObservation
    pagination: SelectionObservation
    single_tool_completion: SelectionObservation


class MarketCoverageResult(FrozenModel):
    market: str = Field(pattern=r"^[A-Z]{2,8}$")
    state: MarketResultState
    passed_rounds: int = Field(ge=0)
    total_rounds: int = Field(ge=1)
    evidence_refs: tuple[EvidenceRef, ...] = ()
    applicability_reason: str | None = None

    @model_validator(mode="after")
    def validate_result(self) -> MarketCoverageResult:
        if self.passed_rounds > self.total_rounds:
            raise ValueError("market passed rounds cannot exceed total rounds")
        if self.state == "verified" and (
            self.passed_rounds != self.total_rounds
            or len(self.evidence_refs) != self.total_rounds
            or self.applicability_reason is not None
        ):
            raise ValueError("verified market requires every round and its evidence")
        if self.state == "provider_negative" and (
            self.passed_rounds != 0
            or len(self.evidence_refs) != self.total_rounds
            or self.applicability_reason is not None
        ):
            raise ValueError("provider-negative market requires complete evidence")
        if self.state == "not_applicable" and (
            self.passed_rounds
            or self.evidence_refs
            or self.applicability_reason is None
        ):
            raise ValueError("not-applicable market requires only its frozen reason")
        return self


class MarketCoverageSnapshot(FrozenModel):
    release_digest: EvidenceRef
    observation_date: date
    results: tuple[MarketCoverageResult, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def require_unique_markets(self) -> MarketCoverageSnapshot:
        markets = [result.market for result in self.results]
        if len(markets) != len(set(markets)):
            raise ValueError("duplicate market coverage result")
        return self


class SelectionSnapshotRow(FrozenModel):
    cap_id: StableId
    provider_id: StableId
    provider_name: str = Field(min_length=1)
    access_path_id: StableId
    access_path_type: AccessPathType
    observation_window: ObservationWindow
    run_observations: RunObservationsSnapshot
    gateway_metrics: GatewayMetricsSnapshot
    qveris_list_price: QVerisListPriceSnapshot
    official_pricing: OfficialPricingSnapshot
    market_coverage: MarketCoverageSnapshot
    agent_interface: AgentInterfaceSnapshot


class SelectionSnapshot(FrozenModel):
    snapshot_id: StableId
    version: SemanticVersion
    edition: date
    cap_id: StableId
    cap_release_digest: EvidenceRef
    market_coverage_release_digest: EvidenceRef
    input_digests: dict[str, object]
    rows: tuple[SelectionSnapshotRow, ...] = Field(min_length=1)
    limitations: tuple[str, ...] = ()
