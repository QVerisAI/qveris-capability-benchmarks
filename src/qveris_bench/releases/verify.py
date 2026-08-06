from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from qveris_bench.models.evidence import EvidenceBundle
from qveris_bench.models.release import BenchmarkRelease
from qveris_bench.models.run import RunCell
from qveris_bench.releases.canonical import canonical_release_bytes, release_digest
from qveris_bench.releases.gate import ReleaseGateError, validate_release_inputs


def verify_release(path: Path, expected_digest: str) -> bool:
    payload: dict[str, Any] = json.loads(path.read_text())
    try:
        release = BenchmarkRelease.model_validate(payload["release"])
        cells = tuple(RunCell.model_validate(cell) for cell in payload["cells"])
        evidence = tuple(
            EvidenceBundle.model_validate(bundle) for bundle in payload["evidence"]
        )
        validate_release_inputs(release, cells, evidence)
    except (KeyError, TypeError, ValueError, ReleaseGateError):
        return False
    return release_digest(canonical_release_bytes(payload)) == expected_digest
