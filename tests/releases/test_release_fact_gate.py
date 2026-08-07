from __future__ import annotations

import pytest

from qveris_bench.models.enums import (
    CellState,
    DimensionState,
    DisclosureLevel,
    LicenseStatus,
    RedactionStatus,
    ReleaseFactType,
)
from qveris_bench.models.evidence import EvidenceBundle
from qveris_bench.models.release import BenchmarkRelease, ReleaseFact
from qveris_bench.models.run import RunCell
from qveris_bench.releases.gate import ReleaseGateError, validate_release_inputs

_DIGEST = "sha256:" + "a" * 64


def _evidence() -> EvidenceBundle:
    return EvidenceBundle(
        evidence_id="ev-1",
        run_key="suite:fp:case:provider:path:direct:1",
        raw_digest=_DIGEST,
        public_digest=_DIGEST,
        redaction_status=RedactionStatus.SANITIZED,
        disclosure_level=DisclosureLevel.SANITIZED_PUBLIC,
        license_status=LicenseStatus.CLEARED,
        extractor_version="1.0.0",
        suite_fingerprint="a" * 64,
    )


def _cell() -> RunCell:
    return RunCell(
        run_key="suite:fp:case:provider:path:direct:1",
        case_id="case",
        case_input={},
        provider_id="provider",
        access_path_id="path",
        mode="direct",
        round=1,
        applicable=True,
        state=CellState.COMPLETED,
    )


def _release(measured: ReleaseFact) -> BenchmarkRelease:
    return BenchmarkRelease(
        release_id="test-release",
        version="1.0.0",
        suite_fingerprint="a" * 64,
        run_plan_digest=_DIGEST,
        evidence_ids=("ev-1",),
        outcome_ids=("out-1",),
        developer_selection_facts=(measured,),
    )


def test_ac2_measured_fact_evidence_must_resolve_to_release_evidence() -> None:
    measured = ReleaseFact(
        fact_type=ReleaseFactType.OUTCOME,
        dimension_state=DimensionState.MEASURED,
        details={"environment_plan": "three direct rounds"},
        evidence_refs=("sha256:" + "b" * 64,),
    )

    with pytest.raises(ReleaseGateError, match="evidence"):
        validate_release_inputs(_release(measured), (_cell(),), (_evidence(),))


def test_ac2_measured_fact_with_resolved_evidence_passes() -> None:
    measured = ReleaseFact(
        fact_type=ReleaseFactType.OUTCOME,
        dimension_state=DimensionState.MEASURED,
        details={"environment_plan": "three direct rounds"},
        evidence_refs=(_DIGEST,),
    )

    validate_release_inputs(_release(measured), (_cell(),), (_evidence(),))
