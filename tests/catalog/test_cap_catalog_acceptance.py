from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

from qveris_bench.catalog.repository import CapCatalogRepository, DuplicateCapError
from qveris_bench.catalog.validation import CapValidationError, validate_cap_file


def _cap_data(cap_id: str = "etf-holdings", version: str = "1.0.0") -> dict:
    return {
        "cap_id": cap_id,
        "version": version,
        "name": "ETF Holdings",
        "business_use": "Compare constituent-level ETF data providers.",
        "scope": ["US-listed ETFs"],
        "exclusions": ["portfolio optimization"],
        "markets": ["US"],
        "asset_types": ["ETF"],
        "sources": [
            {
                "source_type": "external_repository",
                "repository": "https://github.com/QVerisAI/qveris-agent-harness",
                "commit": "95179a8",
                "task_id": "etf-holdings-001",
            }
        ],
    }


def _write_cap(path: Path, data: dict | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data or _cap_data(), sort_keys=False))


def test_ac1_valid_local_cap_file_loads_as_typed_definition(tmp_path: Path) -> None:
    path = tmp_path / "etf_holdings" / "cap.yaml"
    _write_cap(path)

    cap = validate_cap_file(path)

    assert cap.cap_id == "etf-holdings", "AC1 local CAP ID must round-trip"
    assert str(cap.sources[0].repository).startswith("https://github.com/"), (
        "AC1 external provenance must remain attached"
    )


def test_ac2_duplicate_cap_id_and_version_fail_closed(tmp_path: Path) -> None:
    _write_cap(tmp_path / "pack-a" / "cap.yaml")
    _write_cap(tmp_path / "pack-b" / "cap.yaml")

    with pytest.raises(DuplicateCapError, match="etf-holdings@1.0.0"):
        CapCatalogRepository(tmp_path).list()


@pytest.mark.parametrize(
    ("field", "value"),
    [("commit", "not-a-commit"), ("business_use", None)],
)
def test_ac3_invalid_provenance_or_business_use_is_rejected(
    tmp_path: Path, field: str, value: str | None
) -> None:
    data = _cap_data()
    if field == "commit":
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
        _cap_data(cap_id="stock-quote", version="1.0.0"),
    )
    _write_cap(
        tmp_path / "alpha" / "cap.yaml",
        _cap_data(cap_id="etf-holdings", version="1.0.0"),
    )
    _write_cap(
        tmp_path / "_template" / "cap.yaml",
        _cap_data(cap_id="template-cap", version="1.0.0"),
    )

    caps = CapCatalogRepository(tmp_path).list()

    assert [cap.cap_id for cap in caps] == ["etf-holdings", "stock-quote"], (
        "AC5 catalog output must be deterministic and exclude templates"
    )


def test_ac6_customer_question_uses_sanitized_internal_reference(
    tmp_path: Path,
) -> None:
    data = _cap_data()
    data["sources"] = [
        {
            "source_type": "customer_question",
            "internal_reference": "customer-question-2026-08-sanitized-001",
        }
    ]
    path = tmp_path / "cap.yaml"
    _write_cap(path, data)

    cap = validate_cap_file(path)

    assert cap.sources[0].internal_reference.endswith("001"), (
        "AC6 sanitized internal reference must be retained"
    )


def test_ac7_installed_cli_validates_and_lists_caps(tmp_path: Path) -> None:
    path = tmp_path / "etf_holdings" / "cap.yaml"
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
    assert "etf-holdings@1.0.0" in validate_result.stdout, (
        "AC7 validate output must identify the CAP version"
    )
    assert list_result.returncode == 0, f"AC7 cap list failed: {list_result.stderr}"
    assert "etf-holdings@1.0.0" in list_result.stdout, (
        "AC7 list output must identify the CAP version"
    )
