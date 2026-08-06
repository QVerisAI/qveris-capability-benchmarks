from __future__ import annotations

from qveris_bench.evidence.policy import PublicationPolicyError, validate_publication
from qveris_bench.models.enums import CellState
from qveris_bench.models.evidence import EvidenceBundle
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
    cells: tuple[RunCell, ...], evidence: tuple[EvidenceBundle, ...]
) -> None:
    open_cells = [cell.run_key for cell in cells if cell.state not in _TERMINAL]
    if open_cells:
        raise ReleaseGateError("open run cells: " + ", ".join(open_cells))
    if not evidence:
        raise ReleaseGateError("release requires evidence")
    for bundle in evidence:
        try:
            validate_publication(bundle)
        except PublicationPolicyError as exc:
            raise ReleaseGateError("unsafe evidence") from exc
