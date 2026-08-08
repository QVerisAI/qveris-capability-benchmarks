import json
import subprocess
from pathlib import Path

import pytest

from qveris_bench.models.enums import (
    CellState,
    DisclosureLevel,
    FailureAttribution,
    LicenseStatus,
    RedactionStatus,
)
from qveris_bench.models.evidence import EvidenceBundle
from qveris_bench.models.release import BenchmarkRelease
from qveris_bench.models.run import RunCell
from qveris_bench.outcomes.attribution import (
    AttributionError,
    ensure_provider_side_attribution,
)
from qveris_bench.releases.builder import build_release
from qveris_bench.releases.gate import ReleaseGateError, validate_release_inputs
from qveris_bench.releases.verify import verify_release

ROOT = Path(__file__).resolve().parents[2]


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
    state: CellState = CellState.COMPLETED,
    attribution: FailureAttribution | None = None,
) -> RunCell:
    return RunCell(
        run_key="cell-1",
        case_id="case-1",
        provider_id="p-1",
        access_path_id="api-1",
        mode="direct",
        round=1,
        state=state,
        failure_attribution=attribution,
    )


def _release() -> BenchmarkRelease:
    return BenchmarkRelease(
        release_id="release-1",
        version="1.0.0",
        suite_fingerprint="c" * 64,
        run_plan_digest="sha256:" + "d" * 64,
        evidence_ids=("cell-1",),
    )


@pytest.mark.parametrize(
    "attribution",
    (
        FailureAttribution.INVALID_PARAMETERS,
        FailureAttribution.PROVIDER_VALIDATION_ERROR,
        FailureAttribution.PROVIDER_RUNTIME_ERROR,
        FailureAttribution.AUTH_OR_ENTITLEMENT,
        FailureAttribution.RATE_LIMITED,
        FailureAttribution.NETWORK_OR_TIMEOUT,
        FailureAttribution.EMPTY_OR_PARTIAL_DATA,
        FailureAttribution.TRUNCATED_OR_UNPAGED,
    ),
)
def test_ac2_provider_negative_with_provider_side_attribution_passes(
    attribution: FailureAttribution,
) -> None:
    validate_release_inputs(
        _release(), (_cell(CellState.PROVIDER_NEGATIVE, attribution),), (_evidence(),)
    )


def test_ac1_provider_negative_without_attribution_is_rejected() -> None:
    with pytest.raises(ReleaseGateError, match="attribution"):
        validate_release_inputs(
            _release(), (_cell(CellState.PROVIDER_NEGATIVE),), (_evidence(),)
        )


@pytest.mark.parametrize(
    "attribution",
    (
        FailureAttribution.RESPONSE_INTERPRETATION_ERROR,
        FailureAttribution.BENCHMARK_SYSTEM_ERROR,
        FailureAttribution.AGENT_OUTPUT_ERROR,
        FailureAttribution.UNKNOWN,
    ),
)
def test_ac3_ac4_benchmark_or_unattributable_failures_cannot_be_provider_negative(
    attribution: FailureAttribution,
) -> None:
    with pytest.raises(ReleaseGateError, match="provider-side"):
        validate_release_inputs(
            _release(),
            (_cell(CellState.PROVIDER_NEGATIVE, attribution),),
            (_evidence(),),
        )


@pytest.mark.parametrize(
    "state", (CellState.COMPLETED, CellState.EXCLUDED, CellState.NOT_APPLICABLE)
)
def test_ac5_non_provider_negative_cells_do_not_require_attribution(
    state: CellState,
) -> None:
    validate_release_inputs(_release(), (_cell(state),), (_evidence(),))


def test_ac6_build_release_enforces_attribution_by_default() -> None:
    with pytest.raises(ReleaseGateError, match="attribution"):
        build_release(_release(), (_cell(CellState.PROVIDER_NEGATIVE),), (_evidence(),))


def test_ac7_legacy_published_release_still_verifies_by_digest() -> None:
    release_dir = ROOT / "releases/stock-quote-family-2026-q3-v1"
    digest = "sha256:2984a796bee2e9242c818f3336927972fe93030ca13f01f459e7333d5d509f57"

    assert verify_release(release_dir / "release.json", digest)


def test_ac9_attribution_helper_only_accepts_provider_side_causes() -> None:
    ensure_provider_side_attribution(FailureAttribution.EMPTY_OR_PARTIAL_DATA)
    with pytest.raises(AttributionError, match="provider-side"):
        ensure_provider_side_attribution(
            FailureAttribution.RESPONSE_INTERPRETATION_ERROR
        )
    with pytest.raises(AttributionError, match="attribution"):
        ensure_provider_side_attribution(None)


def test_ac9_run_cell_parses_legacy_json_without_attribution_field() -> None:
    legacy = {
        "run_key": "suite:case:provider:direct:1",
        "case_id": "case-1",
        "provider_id": "p-1",
        "access_path_id": "api-1",
        "mode": "direct",
        "round": 1,
        "state": "provider_negative",
    }

    cell = RunCell.model_validate(legacy)

    assert cell.failure_attribution is None


def test_ac10_cli_release_build_rejects_unattributed_provider_negative(
    tmp_path: Path,
) -> None:
    cells = [
        {
            "run_key": "cell-1",
            "case_id": "case-1",
            "provider_id": "p-1",
            "access_path_id": "api-1",
            "mode": "direct",
            "round": 1,
            "state": "provider_negative",
        }
    ]
    evidence = [
        {
            "evidence_id": "cell-1",
            "run_key": "cell-1",
            "raw_digest": "sha256:" + "a" * 64,
            "public_digest": "sha256:" + "b" * 64,
            "redaction_status": "sanitized",
            "disclosure_level": "sanitized_public",
            "license_status": "cleared",
            "extractor_version": "1.0.0",
            "suite_fingerprint": "c" * 64,
        }
    ]
    release = {
        "release_id": "release-1",
        "version": "1.0.0",
        "suite_fingerprint": "c" * 64,
        "run_plan_digest": "sha256:" + "d" * 64,
        "evidence_ids": ["cell-1"],
    }
    (tmp_path / "cells.json").write_text(json.dumps(cells))
    (tmp_path / "evidence.json").write_text(json.dumps(evidence))
    (tmp_path / "release-input.json").write_text(json.dumps(release))

    result = subprocess.run(
        [
            "uv",
            "run",
            "qveris-bench",
            "release",
            "build",
            str(tmp_path / "release-input.json"),
            str(tmp_path / "cells.json"),
            str(tmp_path / "evidence.json"),
            "--output",
            str(tmp_path / "release.json"),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode != 0
    assert "attribution" in result.stderr
