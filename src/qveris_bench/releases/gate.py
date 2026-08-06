from __future__ import annotations

from qveris_bench.evidence.policy import PublicationPolicyError, validate_publication
from qveris_bench.models.enums import CellState
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
    applicable_keys = {cell.run_key for cell in cells if cell.applicable}
    if not applicable_keys <= evidence_ids:
        raise ReleaseGateError("applicable cells require matching evidence")
    for bundle in evidence:
        if bundle.suite_fingerprint != release.suite_fingerprint:
            raise ReleaseGateError("evidence suite fingerprint mismatch")
        try:
            validate_publication(bundle)
        except PublicationPolicyError as exc:
            raise ReleaseGateError("unsafe evidence") from exc
