from qveris_bench.models.enums import (
    CellState,
    DisclosureLevel,
    LicenseStatus,
    RedactionStatus,
)
from qveris_bench.models.evidence import EvidenceBundle
from qveris_bench.models.release import BenchmarkRelease
from qveris_bench.models.run import RunCell
from qveris_bench.releases.builder import build_release


def test_ac3_release_builder_is_reproducible_and_emits_only_facts() -> None:
    release = BenchmarkRelease(
        release_id="release-1",
        version="1.0.0",
        suite_fingerprint="a" * 64,
        run_plan_digest="sha256:" + "b" * 64,
        evidence_ids=("cell-1",),
    )
    cell = RunCell(
        run_key="cell-1",
        case_id="case-1",
        provider_id="p-1",
        access_path_id="api-1",
        mode="direct",
        round=1,
        state=CellState.COMPLETED,
    )
    evidence = EvidenceBundle(
        evidence_id="cell-1",
        run_key="cell-1",
        raw_digest="sha256:" + "c" * 64,
        public_digest="sha256:" + "d" * 64,
        redaction_status=RedactionStatus.SANITIZED,
        disclosure_level=DisclosureLevel.SANITIZED_PUBLIC,
        license_status=LicenseStatus.CLEARED,
        extractor_version="1.0.0",
        suite_fingerprint="a" * 64,
    )

    first = build_release(release, (cell,), (evidence,))
    second = build_release(release, (cell,), (evidence,))

    assert first == second
    assert b"score" not in first.lower()
