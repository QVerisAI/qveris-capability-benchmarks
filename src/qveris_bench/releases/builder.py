from __future__ import annotations

from qveris_bench.models.evidence import EvidenceBundle
from qveris_bench.models.release import BenchmarkRelease
from qveris_bench.models.run import RunCell
from qveris_bench.releases.canonical import canonical_release_bytes
from qveris_bench.releases.gate import validate_release_inputs


def build_release(
    release: BenchmarkRelease,
    cells: tuple[RunCell, ...],
    evidence: tuple[EvidenceBundle, ...],
) -> bytes:
    validate_release_inputs(cells, evidence)
    payload = {
        "release": release.model_dump(mode="json"),
        "cells": [cell.model_dump(mode="json") for cell in cells],
        "evidence": [bundle.model_dump(mode="json") for bundle in evidence],
    }
    return canonical_release_bytes(payload)
