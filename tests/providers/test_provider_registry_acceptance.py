from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

from qveris_bench.providers.qualification import CohortValidationError
from qveris_bench.providers.repository import (
    DuplicateProviderIdentityError,
    ProviderRegistryRepository,
    ProviderValidationError,
)


def _provider_data(
    provider_id: str = "financial-modeling-prep",
    access_path_id: str = "fmp-official-api",
    qualified: bool = True,
) -> dict:
    data = {
        "provider": {
            "provider_id": provider_id,
            "official_name": "Financial Modeling Prep",
            "website": "https://site.financialmodelingprep.com/",
            "market_coverage": ["US"],
            "official_pricing": [
                {
                    "pricing_id": "fmp-official-pricing",
                    "pricing_url": (
                        "https://site.financialmodelingprep.com/pricing-plans"
                    ),
                    "applies_to": "provider_wide",
                    "currencies": ["USD"],
                    "free_tier": "Basic plan with 250 calls per day",
                    "paid_plans": "Starter from USD 22/month",
                    "verified_at": "2026-08-10",
                    "source_digest": "d" * 64,
                    "extractor_version": "1.0.0",
                    "suite_fingerprint": "e" * 64,
                    "disclosure_level": "sanitized_public",
                    "license_status": "cleared",
                }
            ],
        },
        "access_paths": [
            {
                "access_path_id": access_path_id,
                "provider_id": provider_id,
                "path_type": "official_api",
                "official_source": (
                    "https://site.financialmodelingprep.com/developer/docs"
                ),
                "plan_name": "Starter",
                "authorization": "Internal benchmark use",
                "canonical_interface": "etf-holder",
                "protocol": "https_rest",
                "endpoint_url": "https://financialmodelingprep.com/stable",
                "authentication": "API key query parameter",
                "agent_trial_eligible": False,
            }
        ],
    }
    if qualified:
        data["access_paths"][0]["qualification"] = {
            "disposition": "included",
            "reason": "Official interface and approved test credential are available.",
            "evidence_digest": "sha256:" + "a" * 64,
        }
    return data


def _write_provider(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False))


def test_ac1_provider_entity_and_access_paths_load_separately(tmp_path: Path) -> None:
    data = _provider_data()
    second_path = dict(data["access_paths"][0])
    second_path.update(
        {
            "access_path_id": "fmp-qveris-connector",
            "path_type": "qveris_connector",
            "official_source": "https://qveris.ai/",
            "canonical_interface": "fmp-etf-holder",
            "endpoint_url": None,
            "authentication": "Managed access",
        }
    )
    second_path["qualification"] = {
        "disposition": "excluded",
        "reason": "QVeris path is not approved for this frozen cohort.",
        "evidence_digest": "sha256:" + "c" * 64,
    }
    data["access_paths"].append(second_path)
    _write_provider(tmp_path / "fmp" / "provider.yaml", data)

    records = ProviderRegistryRepository(tmp_path).list()

    assert len(records) == 1, "AC1 one Provider entity must remain one record"
    assert [path.access_path_id for path in records[0].access_paths] == [
        "fmp-official-api",
        "fmp-qveris-connector",
    ], "AC1 Native and QVeris Access Paths must remain distinct"
    assert [path.qualification.disposition for path in records[0].access_paths] == [
        "included",
        "excluded",
    ], "AC1 each Access Path must retain its own terminal disposition"


def test_ac2_duplicate_provider_or_access_path_identity_is_rejected(
    tmp_path: Path,
) -> None:
    _write_provider(tmp_path / "a" / "provider.yaml", _provider_data())
    duplicate = _provider_data(access_path_id="fmp-second-api")
    _write_provider(tmp_path / "b" / "provider.yaml", duplicate)

    with pytest.raises(DuplicateProviderIdentityError, match="financial-modeling-prep"):
        ProviderRegistryRepository(tmp_path).list()


def test_ac3_access_path_provider_mismatch_is_rejected(tmp_path: Path) -> None:
    data = _provider_data()
    data["access_paths"][0]["provider_id"] = "different-provider"
    path = tmp_path / "provider.yaml"
    _write_provider(path, data)

    with pytest.raises(ProviderValidationError, match="different-provider"):
        ProviderRegistryRepository(tmp_path).load(path)


def test_ac3_duplicate_yaml_keys_are_rejected(tmp_path: Path) -> None:
    path = tmp_path / "provider.yaml"
    _write_provider(path, _provider_data())
    path.write_text("provider: {}\n" + path.read_text())

    with pytest.raises(ProviderValidationError, match="duplicate key"):
        ProviderRegistryRepository(tmp_path).load(path)


def test_ac4_frozen_cohort_requires_terminal_disposition(tmp_path: Path) -> None:
    _write_provider(
        tmp_path / "fmp" / "provider.yaml",
        _provider_data(qualified=False),
    )
    repository = ProviderRegistryRepository(tmp_path)

    with pytest.raises(CohortValidationError, match="fmp-official-api"):
        repository.cohort_check()


def test_ac4_qveris_path_does_not_require_a_provider_relationship_flag(
    tmp_path: Path,
) -> None:
    data = _provider_data()
    data["access_paths"][0].update(
        {
            "path_type": "qveris_connector",
            "endpoint_url": None,
            "authentication": "Managed access",
        }
    )
    path = tmp_path / "provider.yaml"
    _write_provider(path, data)

    record = ProviderRegistryRepository(tmp_path).load(path)

    assert record.access_paths[0].path_type == "qveris_connector", (
        "AC4 Access Path identity must not leak into the Provider entity"
    )


@pytest.mark.parametrize("disposition", ["included", "excluded"])
def test_ac5_terminal_dispositions_retain_reason_and_evidence(
    tmp_path: Path, disposition: str
) -> None:
    data = _provider_data()
    data["access_paths"][0]["qualification"]["disposition"] = disposition
    path = tmp_path / "provider.yaml"
    _write_provider(path, data)

    record = ProviderRegistryRepository(tmp_path).load(path)

    qualification = record.access_paths[0].qualification
    assert qualification is not None, "AC5 qualification must be terminal"
    assert qualification.disposition == disposition, (
        "AC5 terminal disposition must round-trip"
    )
    assert qualification.evidence_digest.startswith("sha256:"), (
        "AC5 terminal decision must retain evidence"
    )


def test_ac6_fx_qveris_observations_have_registered_access_paths() -> None:
    records = ProviderRegistryRepository(Path("providers")).list()
    path_ids = {
        path.access_path_id for record in records for path in record.access_paths
    }

    assert {
        "alpha-vantage-fx-spot-qveris",
        "twelve-data-fx-spot-qveris",
        "eodhd-fx-spot-qveris",
        "rongjuhui-hkd-reference-rate",
    } <= path_ids


def test_ac8_installed_provider_cli_validates_qualifies_and_checks_cohort(
    tmp_path: Path,
) -> None:
    path = tmp_path / "fmp" / "provider.yaml"
    _write_provider(path, _provider_data(qualified=False))
    executable = shutil.which("qveris-bench")
    assert executable is not None, "AC8 installed CLI is required"

    validate_result = subprocess.run(
        [executable, "provider", "validate", str(path)],
        check=False,
        capture_output=True,
        text=True,
    )
    qualify_result = subprocess.run(
        [
            executable,
            "provider",
            "qualify",
            str(path),
            "--access-path-id",
            "fmp-official-api",
            "--disposition",
            "included",
            "--reason",
            "Official test path approved.",
            "--evidence-digest",
            "sha256:" + "b" * 64,
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    cohort_result = subprocess.run(
        [executable, "provider", "cohort-check", "--root", str(tmp_path)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert validate_result.returncode == 0, (
        f"AC8 provider validate failed: {validate_result.stderr}"
    )
    assert qualify_result.returncode == 0, (
        f"AC8 provider qualify failed: {qualify_result.stderr}"
    )
    assert cohort_result.returncode == 0, (
        f"AC8 cohort-check failed: {cohort_result.stderr}"
    )
    assert "1 provider" in cohort_result.stdout, (
        "AC8 cohort-check must report the frozen cohort size"
    )
