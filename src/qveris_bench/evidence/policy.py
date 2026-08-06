from __future__ import annotations

from qveris_bench.models.enums import DisclosureLevel, LicenseStatus, RedactionStatus
from qveris_bench.models.evidence import EvidenceBundle


class PublicationPolicyError(ValueError):
    pass


def validate_publication(bundle: EvidenceBundle) -> None:
    if bundle.redaction_status is not RedactionStatus.SANITIZED:
        raise PublicationPolicyError("public evidence must be sanitized")
    if bundle.disclosure_level is not DisclosureLevel.SANITIZED_PUBLIC:
        raise PublicationPolicyError(
            "public evidence requires sanitized_public disclosure"
        )
    if bundle.license_status is not LicenseStatus.CLEARED:
        raise PublicationPolicyError("public evidence requires cleared license status")
    if bundle.public_digest is None:
        raise PublicationPolicyError("public evidence requires a public digest")
