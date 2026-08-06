from __future__ import annotations

import re
import shutil
import subprocess
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SECRET_PATTERNS = (
    re.compile(r"sk-[A-Za-z0-9_-]{20,}"),
    re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(
        r"(?i)(?:api[_-]?key|access[_-]?token|secret|password)"
        r"\s*[:=]\s*[\"']?[^\s\"']{8,}"
    ),
)


def _requirement_name(requirement: str) -> str:
    match = re.match(r"\s*([A-Za-z0-9][A-Za-z0-9_.-]*)", requirement)
    assert match is not None, f"Invalid dependency requirement: {requirement}"
    return re.sub(r"[-_.]+", "-", match.group(1)).lower()


def _all_dependency_names(pyproject: dict[str, object]) -> set[str]:
    project = pyproject["project"]
    assert isinstance(project, dict)
    requirements = list(project["dependencies"])
    for group in project.get("optional-dependencies", {}).values():
        requirements.extend(group)

    for group in pyproject.get("dependency-groups", {}).values():
        requirements.extend(group)

    build_system = pyproject["build-system"]
    assert isinstance(build_system, dict)
    requirements.extend(build_system["requires"])
    return {_requirement_name(requirement) for requirement in requirements}


def _is_unsafe_path(path: Path) -> bool:
    lowered_parts = tuple(part.lower() for part in path.parts)
    name = path.name.lower()
    credential_names = {
        "credentials.json",
        "credentials.yaml",
        "credentials.yml",
        "id_dsa",
        "id_ecdsa",
        "id_ed25519",
        "id_rsa",
        "secrets.json",
        "secrets.toml",
        "secrets.yaml",
        "secrets.yml",
        "service-account.json",
    }

    if name.startswith(".env") and name != ".env.example":
        return True
    if name == ".envrc" or name in credential_names:
        return True
    if path.suffix.lower() in {".key", ".p12", ".pem", ".pfx"}:
        return True
    if "raw_artifacts" in lowered_parts:
        return True
    if lowered_parts and lowered_parts[0] in {".runs", "runs"}:
        return True
    if "evidence" in lowered_parts:
        evidence_index = lowered_parts.index("evidence")
        if {"private", "raw"} & set(lowered_parts[evidence_index + 1 :]):
            return True
    return False


def _contains_secret(text: str) -> bool:
    return any(pattern.search(text) for pattern in SECRET_PATTERNS)


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


def test_ac1_governance_defines_a_private_conduct_reporting_route() -> None:
    code_of_conduct = (ROOT / "CODE_OF_CONDUCT.md").read_text(encoding="utf-8")
    security = (ROOT / "SECURITY.md").read_text(encoding="utf-8")

    assert "Conduct Report" in code_of_conduct, (
        "AC1 Code of Conduct must name the private reporting process"
    )
    assert "Conduct Report" in security, (
        "AC1 security policy must explain how to submit conduct reports"
    )
    assert "/security/advisories/new" in security, (
        "AC1 conduct reports need a functioning private intake route"
    )


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
    dependencies = _all_dependency_names(pyproject)
    source = "\n".join(
        path.read_text(encoding="utf-8") for path in (ROOT / "src").rglob("*.py")
    ).lower()

    for forbidden in ("qveris-agent-harness", "harbor"):
        assert _requirement_name(forbidden) not in dependencies, (
            f"AC3 forbidden dependency: {forbidden}"
        )
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


def test_ac4_architecture_preserves_frozen_cap_bounds() -> None:
    architecture = (ROOT / "docs/architecture/platform.md").read_text(encoding="utf-8")

    assert re.search(r"5–8\s+providers and at least three rounds", architecture), (
        "AC4 ETF Holdings must retain its provider and round bounds"
    )
    assert "Stock Quote smoke CAP with two providers" in architecture, (
        "AC4 Stock Quote smoke must retain its provider count"
    )


def test_ac5_tracked_files_exclude_secrets_raw_evidence_and_local_runs() -> None:
    result = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    )
    tracked = [Path(path) for path in result.stdout.decode().split("\0") if path]
    unsafe_paths = [str(path) for path in tracked if _is_unsafe_path(path)]
    secret_files = []
    for path in tracked:
        if _is_unsafe_path(path):
            continue
        contents = (ROOT / path).read_bytes()
        if b"\0" not in contents and _contains_secret(contents.decode(errors="ignore")):
            secret_files.append(str(path))

    assert not unsafe_paths, f"AC5 unsafe files are tracked: {unsafe_paths}"
    assert not secret_files, f"AC5 secret-looking values are tracked: {secret_files}"


def test_ac5_env_example_contains_names_without_values() -> None:
    populated = []
    for line_number, line in enumerate(
        (ROOT / ".env.example").read_text(encoding="utf-8").splitlines(), start=1
    ):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        name, separator, value = stripped.partition("=")
        if not separator or not name or value.strip():
            populated.append(line_number)

    assert not populated, (
        f"AC5 .env.example assignments must be present and empty: lines {populated}"
    )


def test_ac5_adversarial_unsafe_paths_are_rejected() -> None:
    unsafe_examples = (
        ".env.local",
        ".env.production",
        ".envrc",
        "credentials.json",
        "provider/service-account.json",
        "private-key.p12",
        "id_rsa",
        "raw_artifacts/response.json",
        "evidence/provider/raw/response.json",
        "evidence/private/provider.json",
        "runs/local/state.json",
    )

    missed = [path for path in unsafe_examples if not _is_unsafe_path(Path(path))]
    assert not missed, f"AC5 unsafe-path guard misses: {missed}"
    assert not _is_unsafe_path(Path(".env.example")), (
        "AC5 empty credential-name examples must remain committable"
    )


def test_ac5_secret_fingerprints_are_rejected() -> None:
    secret_examples = (
        "sk-" + "A" * 24,
        "ghp_" + "B" * 24,
        "AKIA" + "C" * 16,
        "api_key=" + "D" * 20,
        "-----BEGIN PRIVATE " + "KEY-----",
    )

    missed = [secret for secret in secret_examples if not _contains_secret(secret)]
    assert not missed, "AC5 content guard misses a secret fingerprint"


def test_ac6_python_and_quality_tooling_match_the_frozen_stack() -> None:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    dependencies = {
        _requirement_name(requirement)
        for requirement in pyproject["project"]["dependencies"]
    }
    dev_dependencies = {
        _requirement_name(requirement)
        for requirement in pyproject["dependency-groups"]["dev"]
    }

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


def test_ac6_ci_repeats_the_locked_local_quality_gates() -> None:
    workflow = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    replay = (ROOT / "docs/release-replay.md").read_text(encoding="utf-8")

    for command in (
        "uv sync --locked --all-groups",
        "uv run pytest -q",
        "uv run ruff check .",
        "uv run ruff format --check .",
        "uv run mypy src",
        "uv run qveris-bench schema export --check",
    ):
        assert command in workflow
    assert "must not invoke\nprovider APIs" in replay
    assert "credential values remain outside" in replay


def test_ac7_cli_help_runs_in_a_real_subprocess() -> None:
    executable = shutil.which("qveris-bench")
    assert executable is not None, "AC7 installed qveris-bench entry point is missing"
    result = subprocess.run(
        [executable, "--help"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, f"AC7 CLI failed: {result.stderr}"
    assert "qveris-bench" in result.stdout.lower(), "AC7 CLI help is missing its name"
