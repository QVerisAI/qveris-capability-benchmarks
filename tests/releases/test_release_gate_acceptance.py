import pytest

from qveris_bench.models.enums import (
    CellState,
    DisclosureLevel,
    LicenseStatus,
    RedactionStatus,
)
from qveris_bench.models.evidence import EvidenceBundle
from qveris_bench.models.release import BenchmarkRelease
from qveris_bench.models.run import RunCell
from qveris_bench.releases.gate import ReleaseGateError, validate_release_inputs


def _evidence() -> EvidenceBundle:
    return EvidenceBundle(
        evidence_id="cell-1",
        run_key="cell-1",
        raw_digest="sha256:" + "a" * 64,
        public_digest="sha256:" + "b" * 64,
        redaction_status=RedactionStatus.SANITIZED,
        disclosure_level=DisclosureLevel.SANITIZED_PUBLIC,
        license_status=LicenseStatus.CLEARED,
        extractor_version="1.0.0",
        suite_fingerprint="c" * 64,
    )


def _cell(
    state: CellState = CellState.COMPLETED, access_path_id: str = "api-1"
) -> RunCell:
    return RunCell(
        run_key="cell-1",
        case_id="case-1",
        provider_id="p-1",
        access_path_id=access_path_id,
        mode="direct",
        round=1,
        state=state,
    )


def _release() -> BenchmarkRelease:
    return BenchmarkRelease(
        release_id="release-1",
        version="1.0.0",
        suite_fingerprint="c" * 64,
        run_plan_digest="sha256:" + "d" * 64,
        evidence_ids=("cell-1",),
    )


def test_ac1_release_gate_accepts_terminal_cells_with_safe_evidence() -> None:
    validate_release_inputs(_release(), (_cell(),), (_evidence(),))


def test_ac1_release_gate_rejects_open_cells() -> None:
    with pytest.raises(ReleaseGateError, match="open"):
        validate_release_inputs(_release(), (_cell(CellState.PLANNED),), (_evidence(),))


def test_ac1_release_gate_rejects_missing_evidence() -> None:
    with pytest.raises(ReleaseGateError, match="evidence"):
        validate_release_inputs(_release(), (_cell(),), ())


def test_ac1_release_gate_binds_colon_run_keys_without_weakening_evidence_ids() -> None:
    cell = _cell()
    cell = cell.model_copy(update={"run_key": "suite:case:provider:direct:1"})
    evidence = _evidence().model_copy(update={"run_key": cell.run_key})

    validate_release_inputs(_release(), (cell,), (evidence,))


def test_ac1_release_gate_rejects_orphan_evidence_run_key() -> None:
    evidence = _evidence().model_copy(update={"run_key": "unrelated:run:key"})

    with pytest.raises(ReleaseGateError, match="matching evidence"):
        validate_release_inputs(_release(), (_cell(),), (evidence,))


def test_ac1_release_gate_rejects_duplicate_applicable_cell_run_keys() -> None:
    duplicate = _cell().model_copy(update={"case_id": "case-2"})

    with pytest.raises(ReleaseGateError, match="duplicate applicable"):
        validate_release_inputs(_release(), (_cell(), duplicate), (_evidence(),))
