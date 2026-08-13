from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

from qveris_bench.catalog.repository import CapCatalogRepository, DuplicateCapError
from qveris_bench.catalog.validation import CapValidationError, validate_cap_file


def _cap_data(cap_id: str = "dividend-events", version: str = "1.0.0") -> dict:
    return {
        "cap_id": cap_id,
        "version": version,
        "name": "Dividend Events",
        "business_use": "Compare provider paths for dated dividend events.",
        "scope": ["Dated issuer dividend events"],
        "exclusions": ["portfolio optimization"],
        "markets": ["US"],
        "asset_types": ["EQUITY"],
        "sources": [
            {
                "source_type": "harbor_catalog",
                "harbor_capability_id": "MKT.DIVIDENDS",
                "contract_version": 1,
                "catalog_snapshot_digest": "a" * 64,
                "contract_digest": "b" * 64,
            }
        ],
    }


def _write_cap(path: Path, data: dict | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data or _cap_data(), sort_keys=False))


def test_ac1_valid_local_cap_file_loads_as_typed_definition(tmp_path: Path) -> None:
    path = tmp_path / "dividend_events" / "cap.yaml"
    _write_cap(path)

    cap = validate_cap_file(path)

    assert cap.cap_id == "dividend-events", "AC1 local CAP ID must round-trip"
    assert cap.sources[0].harbor_capability_id == "MKT.DIVIDENDS", (
        "AC1 formal CAP must retain its Harbor capability identity"
    )


def test_ac2_duplicate_cap_id_and_version_fail_closed(tmp_path: Path) -> None:
    _write_cap(tmp_path / "pack-a" / "cap.yaml")
    _write_cap(tmp_path / "pack-b" / "cap.yaml")

    with pytest.raises(DuplicateCapError, match="dividend-events@1.0.0"):
        CapCatalogRepository(tmp_path).list()


@pytest.mark.parametrize(
    ("field", "value"),
    [("contract_digest", "not-a-digest"), ("business_use", None)],
)
def test_ac3_invalid_provenance_or_business_use_is_rejected(
    tmp_path: Path, field: str, value: str | None
) -> None:
    data = _cap_data()
    if field == "contract_digest":
        data["sources"][0][field] = value
    else:
        data.pop(field)
    path = tmp_path / "cap.yaml"
    _write_cap(path, data)

    with pytest.raises(CapValidationError, match=field):
        validate_cap_file(path)


def test_ac4_non_mapping_yaml_is_rejected_with_path(tmp_path: Path) -> None:
    path = tmp_path / "cap.yaml"
    path.write_text("- not\n- a\n- mapping\n")

    with pytest.raises(CapValidationError, match=str(path)):
        validate_cap_file(path)


def test_ac4_duplicate_yaml_keys_are_rejected(tmp_path: Path) -> None:
    path = tmp_path / "cap.yaml"
    _write_cap(path)
    path.write_text("cap_id: duplicate\n" + path.read_text())

    with pytest.raises(CapValidationError, match="duplicate key"):
        validate_cap_file(path)


def test_ac5_catalog_is_sorted_and_skips_template_directory(tmp_path: Path) -> None:
    _write_cap(
        tmp_path / "zeta" / "cap.yaml",
        _cap_data(cap_id="dividend-events", version="1.0.0"),
    )
    _write_cap(
        tmp_path / "alpha" / "cap.yaml",
        _cap_data(cap_id="realtime-financial-news", version="1.0.0"),
    )
    _write_cap(
        tmp_path / "_template" / "cap.yaml",
        _cap_data(cap_id="template-cap", version="1.0.0"),
    )

    caps = CapCatalogRepository(tmp_path).list()

    assert [cap.cap_id for cap in caps] == [
        "dividend-events",
        "realtime-financial-news",
    ], "AC5 catalog output must be deterministic and exclude templates"


def test_ac6_non_harbor_cap_source_is_rejected(tmp_path: Path) -> None:
    data = _cap_data()
    data["sources"] = [
        {
            "source_type": "customer_question",
            "internal_reference": "customer-question-2026-08-sanitized-001",
        }
    ]
    path = tmp_path / "cap.yaml"
    _write_cap(path, data)

    with pytest.raises(CapValidationError, match="source_type"):
        validate_cap_file(path)


@pytest.mark.parametrize(
    "missing",
    [
        "harbor_capability_id",
        "contract_version",
        "catalog_snapshot_digest",
        "contract_digest",
    ],
)
def test_ac6_harbor_cap_requires_immutable_contract_provenance(
    tmp_path: Path, missing: str
) -> None:
    data = _cap_data()
    data["sources"][0].pop(missing)
    path = tmp_path / "cap.yaml"
    _write_cap(path, data)

    with pytest.raises(CapValidationError, match=missing):
        validate_cap_file(path)


def test_ac7_installed_cli_validates_and_lists_caps(tmp_path: Path) -> None:
    path = tmp_path / "dividend_events" / "cap.yaml"
    _write_cap(path)
    executable = shutil.which("qveris-bench")
    assert executable is not None, "AC7 installed CLI is required"

    validate_result = subprocess.run(
        [executable, "cap", "validate", str(path)],
        check=False,
        capture_output=True,
        text=True,
    )
    list_result = subprocess.run(
        [executable, "cap", "list", "--root", str(tmp_path)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert validate_result.returncode == 0, (
        f"AC7 cap validate failed: {validate_result.stderr}"
    )
    assert "dividend-events@1.0.0" in validate_result.stdout, (
        "AC7 validate output must identify the CAP version"
    )
    assert list_result.returncode == 0, f"AC7 cap list failed: {list_result.stderr}"
    assert "dividend-events@1.0.0" in list_result.stdout, (
        "AC7 list output must identify the CAP version"
    )
