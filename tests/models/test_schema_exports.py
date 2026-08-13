from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from qveris_bench.models.schema_export import check_schemas, export_schemas

EXPECTED_SCHEMAS = {
    "access-path.schema.json",
    "benchmark-release.schema.json",
    "benchmark-suite.schema.json",
    "cap-definition.schema.json",
    "evidence-bundle.schema.json",
    "provider-profile.schema.json",
    "publication-package.schema.json",
    "run-plan.schema.json",
    "selection-snapshot.schema.json",
    "task-outcome.schema.json",
}


def test_ac8_schema_exports_are_deterministic_and_type_metric_score_fields(
    tmp_path: Path,
) -> None:
    export_schemas(tmp_path)
    first = {path.name: path.read_bytes() for path in tmp_path.glob("*.json")}
    export_schemas(tmp_path)
    second = {path.name: path.read_bytes() for path in tmp_path.glob("*.json")}

    assert set(first) == EXPECTED_SCHEMAS, "AC8 all public root schemas must export"
    assert first == second, "AC8 repeated schema export must be byte-identical"
    assert check_schemas(tmp_path), "AC8 fresh schema export must pass --check"

    combined = b"\n".join(first.values()).lower()
    assert b'"metricscore"' in combined, "AC8 typed dimension scores must export"
    assert b'"metricranking"' in combined, "AC8 typed dimension ranks must export"
    for forbidden in (
        b'"provider_score"',
        b'"agent_friendly_rating"',
        b"wrong_tool_selected",
    ):
        assert forbidden not in combined, f"AC8 forbidden schema field: {forbidden!r}"


def test_ac8_schema_check_detects_drift(tmp_path: Path) -> None:
    export_schemas(tmp_path)
    target = tmp_path / "cap-definition.schema.json"
    target.write_text("{}\n", encoding="utf-8")

    assert not check_schemas(tmp_path), "AC8 schema drift must fail closed"


def test_ac8_installed_cli_exports_schemas(tmp_path: Path) -> None:
    executable = shutil.which("qveris-bench")
    assert executable is not None, "AC8 installed CLI entry point is required"
    result = subprocess.run(
        [executable, "schema", "export", "--output-dir", str(tmp_path)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, f"AC8 schema export CLI failed: {result.stderr}"
    assert {path.name for path in tmp_path.glob("*.json")} == EXPECTED_SCHEMAS, (
        "AC8 CLI must emit the complete schema set"
    )
