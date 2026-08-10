from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from qveris_bench.models.provider import (
    AccessPath,
    OfficialPricingFact,
    ProviderProfile,
)
from qveris_bench.providers.repository import (
    ProviderRegistryRepository,
    ProviderValidationError,
)


def _pricing(*, applies_to: str | list[str] = "provider_wide") -> dict:
    return {
        "pricing_id": "fmp-official-pricing",
        "pricing_url": "https://site.financialmodelingprep.com/pricing-plans",
        "applies_to": applies_to,
        "currencies": ["USD"],
        "free_tier": "Basic plan with 250 calls per day",
        "paid_plans": "Starter from USD 22/month when billed annually",
        "verified_at": "2026-08-10",
        "source_digest": "a" * 64,
        "extractor_version": "1.0.0",
        "suite_fingerprint": "b" * 64,
        "disclosure_level": "sanitized_public",
        "license_status": "cleared",
    }


def _provider_document(*, applies_to: str | list[str] = "provider_wide") -> dict:
    return {
        "provider": {
            "provider_id": "financial-modeling-prep",
            "official_name": "Financial Modeling Prep",
            "website": "https://financialmodelingprep.com/",
            "market_coverage": ["US"],
            "official_pricing": [_pricing(applies_to=applies_to)],
        },
        "access_paths": [
            {
                "access_path_id": "fmp-official-api",
                "provider_id": "financial-modeling-prep",
                "path_type": "official_api",
                "official_source": (
                    "https://site.financialmodelingprep.com/developer/docs/stable"
                ),
                "canonical_interface": "income-statement",
                "protocol": "https_rest",
                "endpoint_url": "https://financialmodelingprep.com/stable",
                "authentication": "API key query parameter",
                "authorization": "Public paid API plan permits benchmark execution.",
                "agent_trial_eligible": False,
                "qualification": {
                    "disposition": "included",
                    "reason": (
                        "Official interface is authorized for the frozen test cohort."
                    ),
                    "evidence_digest": "sha256:" + "c" * 64,
                },
            }
        ],
    }


def _write(path: Path, document: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(document, sort_keys=False), encoding="utf-8")


def test_ac2_official_pricing_retains_public_fact_provenance() -> None:
    fact = OfficialPricingFact.model_validate(_pricing())

    assert fact.applies_to == "provider_wide", "AC2 pricing scope must round-trip"
    assert fact.currencies == ("USD",), "AC2 original currency must round-trip"
    assert fact.source_digest == "a" * 64, "AC2 source digest must round-trip"
    assert fact.suite_fingerprint == "b" * 64, (
        "AC2 pricing verification suite must round-trip"
    )


@pytest.mark.parametrize(
    "field",
    [
        "pricing_url",
        "applies_to",
        "currencies",
        "verified_at",
        "source_digest",
        "extractor_version",
        "suite_fingerprint",
        "disclosure_level",
        "license_status",
    ],
)
def test_ac2_official_pricing_rejects_missing_provenance(field: str) -> None:
    data = _pricing()
    data.pop(field)

    with pytest.raises(ValidationError, match=field):
        OfficialPricingFact.model_validate(data)


def test_ac1_provider_identity_rejects_path_relationship_fields() -> None:
    data = _provider_document()["provider"]
    data["qveris_integration"] = False
    data["testing_authorization"] = "Native-only supplier"

    with pytest.raises(
        ValidationError, match="qveris_integration|testing_authorization"
    ):
        ProviderProfile.model_validate(data)


def test_ac1_access_path_rejects_catalog_credential_references() -> None:
    data = _provider_document()["access_paths"][0]
    data["credential_env"] = ["FMP_API_KEY"]

    with pytest.raises(ValidationError, match="credential_env"):
        AccessPath.model_validate(data)


def test_ac2_pricing_scope_rejects_unknown_access_path(tmp_path: Path) -> None:
    path = tmp_path / "provider.yaml"
    _write(path, _provider_document(applies_to=["missing-access-path"]))

    with pytest.raises(ProviderValidationError, match="missing-access-path"):
        ProviderRegistryRepository(tmp_path).load(path)


def test_ac1_public_provider_projection_has_no_private_catalog_fields() -> None:
    root = Path(__file__).resolve().parents[2]
    forbidden = (
        "provider_id_alias",
        "credential_ref",
        "credential_reference",
        "credential_env",
        "qveris_integration",
    )
    paths = [
        *sorted((root / "providers").rglob("*.yaml")),
        root / "schemas/provider-profile.schema.json",
        root / "schemas/access-path.schema.json",
        root / "docs/adding-a-provider.md",
    ]

    for path in paths:
        text = path.read_text(encoding="utf-8")
        for token in forbidden:
            assert token not in text, f"AC1 {path} exposes forbidden field {token}"


def test_ac4_published_pricing_facts_bind_the_official_source_record() -> None:
    root = Path(__file__).resolve().parents[2]
    source_record = (root / "docs/provider-access-and-billing-sources.md").read_text(
        encoding="utf-8"
    )
    records = ProviderRegistryRepository(root / "providers").list()

    assert len(records) >= 11, "AC4 the published Provider cohort must be complete"
    for record in records:
        for pricing in record.provider.official_pricing:
            assert str(pricing.pricing_url) in source_record, (
                f"AC4 {pricing.pricing_id} must retain its official source URL"
            )
            assert pricing.source_digest in source_record, (
                f"AC4 {pricing.pricing_id} must bind the recorded source content"
            )
