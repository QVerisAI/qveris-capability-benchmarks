from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import Field, HttpUrl, model_validator

from qveris_bench.models.base import EvidenceRef, FrozenModel, SemanticVersion, StableId

SelectionState = Literal[
    "measured", "declared", "evidence_insufficient", "not_applicable"
]


class ObservationWindow(FrozenModel):
    start: date
    end: date


class GatewayMetricsSnapshot(FrozenModel):
    state: SelectionState
    measurement_boundary: Literal["qveris_gateway"] = "qveris_gateway"
    latency_sample_size: int = Field(ge=0)
    latency_min_ms: float | None = Field(default=None, ge=0)
    latency_median_ms: float | None = Field(default=None, ge=0)
    latency_max_ms: float | None = Field(default=None, ge=0)
    cost_sample_size: int = Field(ge=0)
    median_credits: float | None = Field(default=None, ge=0)
    evidence_refs: tuple[EvidenceRef, ...] = ()

    @model_validator(mode="after")
    def validate_measurement(self) -> GatewayMetricsSnapshot:
        if self.state == "measured" and (
            not self.evidence_refs or self.latency_sample_size == 0
        ):
            raise ValueError("measured gateway metrics require samples and evidence")
        if self.state == "not_applicable" and (
            self.evidence_refs or self.latency_sample_size or self.cost_sample_size
        ):
            raise ValueError("not-applicable gateway metrics cannot carry observations")
        return self


class RunObservationsSnapshot(FrozenModel):
    state: SelectionState
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
        return self


class OfficialPricingSnapshot(FrozenModel):
    state: SelectionState
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
            self.extractor_version,
            self.suite_fingerprint,
            self.disclosure_level,
            self.license_status,
        )
        if self.state == "declared" and any(item is None for item in required):
            raise ValueError("declared pricing requires complete provenance")
        return self


class SelectionObservation(FrozenModel):
    state: SelectionState
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
        if self.state == "evidence_insufficient" and self.evidence_refs:
            raise ValueError("insufficient observation cannot carry evidence")
        return self


class AgentInterfaceSnapshot(FrozenModel):
    invalid_input_handling: SelectionObservation
    parameter_clarity: SelectionObservation
    schema_stability: SelectionObservation
    pagination: SelectionObservation
    single_tool_completion: SelectionObservation


class MarketCoverageSnapshot(FrozenModel):
    tested_markets: tuple[str, ...] = ()
    tested_evidence_refs: tuple[EvidenceRef, ...] = ()
    sv_namespace: str = Field(min_length=1)
    sv_state: SelectionState
    sv_verified_markets: tuple[str, ...] = ()
    sv_evidence_refs: tuple[EvidenceRef, ...] = ()

    @model_validator(mode="after")
    def validate_evidence(self) -> MarketCoverageSnapshot:
        if self.tested_markets and not self.tested_evidence_refs:
            raise ValueError("tested markets require Direct Test evidence")
        if self.sv_state == "measured" and not self.sv_evidence_refs:
            raise ValueError("measured SV coverage requires evidence")
        if self.sv_state in {"evidence_insufficient", "not_applicable"} and (
            self.sv_verified_markets or self.sv_evidence_refs
        ):
            raise ValueError("unmeasured SV coverage cannot carry verified markets")
        return self


class SelectionSnapshotRow(FrozenModel):
    cap_id: StableId
    provider_id: StableId
    provider_name: str = Field(min_length=1)
    access_path_id: StableId
    access_path_type: str = Field(min_length=1)
    observation_window: ObservationWindow
    run_observations: RunObservationsSnapshot
    gateway_metrics: GatewayMetricsSnapshot
    official_pricing: OfficialPricingSnapshot
    market_coverage: MarketCoverageSnapshot
    agent_interface: AgentInterfaceSnapshot


class SelectionSnapshot(FrozenModel):
    snapshot_id: StableId
    version: SemanticVersion
    edition: date
    cap_id: StableId
    cap_release_digest: EvidenceRef
    input_digests: dict[str, object]
    rows: tuple[SelectionSnapshotRow, ...] = Field(min_length=1)
    limitations: tuple[str, ...] = ()
