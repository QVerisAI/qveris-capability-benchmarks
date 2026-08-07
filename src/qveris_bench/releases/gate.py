from __future__ import annotations

from qveris_bench.evidence.policy import PublicationPolicyError, validate_publication
from qveris_bench.models.enums import CellState, DimensionState
from qveris_bench.models.evidence import EvidenceBundle
from qveris_bench.models.release import BenchmarkRelease
from qveris_bench.models.run import RunCell


class ReleaseGateError(ValueError):
    pass


_TERMINAL = {
    CellState.COMPLETED,
    CellState.PROVIDER_NEGATIVE,
    CellState.EXCLUDED,
    CellState.NOT_APPLICABLE,
}


def validate_release_inputs(
    release: BenchmarkRelease,
    cells: tuple[RunCell, ...],
    evidence: tuple[EvidenceBundle, ...],
) -> None:
    open_cells = [cell.run_key for cell in cells if cell.state not in _TERMINAL]
    if open_cells:
        raise ReleaseGateError("open run cells: " + ", ".join(open_cells))
    if not evidence:
        raise ReleaseGateError("release requires evidence")
    evidence_ids = {bundle.evidence_id for bundle in evidence}
    if len(evidence_ids) != len(evidence):
        raise ReleaseGateError("duplicate evidence IDs")
    if set(release.evidence_ids) != evidence_ids:
        raise ReleaseGateError("release evidence IDs do not match evidence bundles")
    cell_run_keys = [cell.run_key for cell in cells]
    if len(set(cell_run_keys)) != len(cell_run_keys):
        raise ReleaseGateError("duplicate cell run keys")
    applicable_run_keys = [cell.run_key for cell in cells if cell.applicable]
    applicable_keys = set(applicable_run_keys)
    evidence_run_keys = [bundle.run_key for bundle in evidence]
    if len(set(evidence_run_keys)) != len(evidence_run_keys):
        raise ReleaseGateError("duplicate evidence run keys")
    if applicable_keys != set(evidence_run_keys):
        raise ReleaseGateError("applicable cells require matching evidence")
    for bundle in evidence:
        if bundle.suite_fingerprint != release.suite_fingerprint:
            raise ReleaseGateError("evidence suite fingerprint mismatch")
        try:
            validate_publication(bundle)
        except PublicationPolicyError as exc:
            raise ReleaseGateError("unsafe evidence") from exc
    available_digests = {
        digest
        for bundle in evidence
        for digest in (bundle.raw_digest, bundle.public_digest)
        if digest is not None
    }
    measured_refs = {
        str(reference)
        for fact in (
            release.developer_selection_facts
            + tuple(
                reference
                for feedback in release.provider_feedback_facts.values()
                for reference in feedback
            )
        )
        if fact.dimension_state == DimensionState.MEASURED
        for reference in fact.evidence_refs
    }
    missing_refs = measured_refs - available_digests
    if missing_refs:
        raise ReleaseGateError(
            "measured dimension facts reference missing evidence: "
            + ", ".join(sorted(missing_refs))
        )
