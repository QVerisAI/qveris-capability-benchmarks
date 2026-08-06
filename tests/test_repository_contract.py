from __future__ import annotations

import subprocess
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_ac1_required_repository_files_exist_and_are_nonempty() -> None:
    required_files = (
        "README.md",
        "AGENTS.md",
        "LICENSE",
        "DATA_LICENSE.md",
        "CONTRIBUTING.md",
        "SECURITY.md",
        "CODE_OF_CONDUCT.md",
        "docs/architecture/platform.md",
        "pyproject.toml",
        ".python-version",
        ".gitignore",
        ".env.example",
        "src/qveris_bench/__init__.py",
        "src/qveris_bench/cli.py",
    )

    missing = [path for path in required_files if not (ROOT / path).is_file()]
    empty = [
        path
        for path in required_files
        if (ROOT / path).is_file() and (ROOT / path).stat().st_size == 0
    ]

    assert not missing, f"AC1 missing required files: {missing}"
    assert not empty, f"AC1 required files must be non-empty: {empty}"


def test_ac2_code_and_data_license_boundaries_are_explicit() -> None:
    code_license = (ROOT / "LICENSE").read_text(encoding="utf-8")
    data_license = (ROOT / "DATA_LICENSE.md").read_text(encoding="utf-8")

    assert "Apache License" in code_license, "AC2 code must use Apache-2.0"
    assert "Version 2.0" in code_license, "AC2 Apache license version must be explicit"
    assert "CC BY 4.0" in data_license, "AC2 QVeris-authored data license is missing"
    assert "third-party" in data_license.lower(), (
        "AC2 third-party artifacts must preserve their source licenses"
    )


def test_ac3_package_is_greenfield_and_has_no_harness_or_harbor_dependency() -> None:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    dependencies = "\n".join(pyproject["project"]["dependencies"]).lower()
    source = "\n".join(
        path.read_text(encoding="utf-8") for path in (ROOT / "src").rglob("*.py")
    ).lower()

    for forbidden in ("qveris-agent-harness", "harbor"):
        assert forbidden not in dependencies, f"AC3 forbidden dependency: {forbidden}"
        assert forbidden not in source, f"AC3 forbidden source dependency: {forbidden}"


def test_ac4_agents_rules_encode_platform_guardrails() -> None:
    rules = (ROOT / "AGENTS.md").read_text(encoding="utf-8").lower()
    required_rules = (
        "cap-specific",
        "access path",
        "aggregate score",
        "single canonical tool",
        "credentials",
        "raw evidence",
        "direct test",
    )

    missing = [rule for rule in required_rules if rule not in rules]
    assert not missing, f"AC4 missing AGENTS.md guardrails: {missing}"


def test_ac5_tracked_files_exclude_secrets_raw_evidence_and_local_runs() -> None:
    result = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    )
    tracked = [Path(path) for path in result.stdout.decode().split("\0") if path]
    unsafe = []

    for path in tracked:
        parts = path.parts
        if path.name == ".env" or path.suffix in {".key", ".pem"}:
            unsafe.append(str(path))
        elif parts[:2] in {("evidence", "raw"), ("evidence", "private")}:
            unsafe.append(str(path))
        elif parts and parts[0] in {"runs", ".runs"}:
            unsafe.append(str(path))

    assert not unsafe, f"AC5 unsafe files are tracked: {unsafe}"


def test_ac6_python_and_quality_tooling_match_the_frozen_stack() -> None:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    dependencies = "\n".join(pyproject["project"]["dependencies"]).lower()
    dev_dependencies = "\n".join(pyproject["dependency-groups"]["dev"]).lower()

    assert pyproject["project"]["requires-python"].startswith(">=3.12"), (
        "AC6 Python 3.12 must be the minimum supported version"
    )
    for dependency in ("pydantic", "typer", "httpx", "pyyaml", "mcp", "openai"):
        assert dependency in dependencies, (
            f"AC6 missing runtime dependency: {dependency}"
        )
    for dependency in ("pytest", "ruff", "mypy"):
        assert dependency in dev_dependencies, (
            f"AC6 missing dev dependency: {dependency}"
        )


def test_ac7_cli_help_runs_in_a_real_subprocess() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "qveris_bench.cli", "--help"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, f"AC7 CLI failed: {result.stderr}"
    assert "qveris-bench" in result.stdout.lower(), "AC7 CLI help is missing its name"
