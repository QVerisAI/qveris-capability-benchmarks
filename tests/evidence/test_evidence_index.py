from pathlib import Path

import pytest

from qveris_bench.evidence.index import EvidenceIndex, EvidenceIndexEntry
from qveris_bench.evidence.policy import PublicationPolicyError, validate_publication
from qveris_bench.models.enums import DisclosureLevel, LicenseStatus, RedactionStatus
from qveris_bench.models.evidence import EvidenceBundle


def _bundle(**overrides: object) -> EvidenceBundle:
    values: dict[str, object] = {
        "evidence_id": "cell-1",
        "run_key": "suite:cell:provider:direct:1",
        "raw_digest": "sha256:" + "a" * 64,
        "public_digest": "sha256:" + "b" * 64,
        "redaction_status": RedactionStatus.SANITIZED,
        "disclosure_level": DisclosureLevel.SANITIZED_PUBLIC,
        "license_status": LicenseStatus.CLEARED,
        "extractor_version": "1.0.0",
        "suite_fingerprint": "c" * 64,
    }
    values.update(overrides)
    return EvidenceBundle(**values)


def test_ac3_evidence_index_is_deterministic_and_retains_provenance(
    tmp_path: Path,
) -> None:
    entry = EvidenceIndexEntry.from_bundle(_bundle())
    index = EvidenceIndex((entry,))

    first = index.write(tmp_path / "index.json")
    second = index.render()

    assert first == second
    assert '"extractor_version": "1.0.0"' in second.decode()
    assert '"suite_fingerprint": "' in second.decode()
    assert '"run_key": "suite:cell:provider:direct:1"' in second.decode()


@pytest.mark.parametrize(
    "overrides",
    [
        {"public_digest": None},
        {"redaction_status": RedactionStatus.PENDING},
        {"license_status": LicenseStatus.PENDING},
        {"disclosure_level": DisclosureLevel.PRIVATE},
    ],
)
def test_ac4_publication_blocks_incomplete_or_unsafe_evidence(
    overrides: dict[str, object],
) -> None:
    with pytest.raises(PublicationPolicyError):
        validate_publication(_bundle(**overrides))
