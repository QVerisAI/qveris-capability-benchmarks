from __future__ import annotations

import builtins
import json
import shutil
import socket
import subprocess
from pathlib import Path
from typing import Any

import httpx
import pytest
from typer.testing import CliRunner

from qveris_bench.cli import app
from qveris_bench.evidence.hashing import sha256_digest
from qveris_bench.releases.canonical import canonical_release_bytes, release_digest

ROOT = Path(__file__).resolve().parents[2]
RELEASES = tuple(
    sorted(path for path in (ROOT / "releases").iterdir() if path.is_dir())
)
REFERENCE_RELEASE = ROOT / "releases/etf-holdings-2026-q3-v1"
REQUIRED_FILES = (
    "release-input.json",
    "run-plan.json",
    "cells.json",
    "evidence.json",
    "release.json",
)
RUNNER = CliRunner()


def _tree_snapshot(path: Path) -> dict[str, bytes]:
    return {
        str(item.relative_to(path)): item.read_bytes()
        for item in path.rglob("*")
        if item.is_file()
    }


def _copy_release(
    tmp_path: Path,
    source: Path = REFERENCE_RELEASE,
) -> Path:
    release_dir = tmp_path / "release"
    shutil.copytree(source, release_dir)
    return release_dir


def _rewrite_plan(
    release_dir: Path,
    mutate: Any,
) -> None:
    plan_path = release_dir / "run-plan.json"
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    mutate(plan)
    plan_bytes = canonical_release_bytes(plan)
    plan_path.write_bytes(plan_bytes)
    plan_digest = sha256_digest(plan_bytes)

    release_input_path = release_dir / "release-input.json"
    release_input = json.loads(release_input_path.read_text(encoding="utf-8"))
    release_input["run_plan_digest"] = plan_digest
    release_input_path.write_bytes(canonical_release_bytes(release_input))

    published_path = release_dir / "release.json"
    published = json.loads(published_path.read_text(encoding="utf-8"))
    published["release"]["run_plan_digest"] = plan_digest
    published_path.write_bytes(canonical_release_bytes(published))


def _rewrite_cells(release_dir: Path, mutate: Any) -> None:
    cells_path = release_dir / "cells.json"
    cells = json.loads(cells_path.read_text(encoding="utf-8"))
    mutate(cells)
    cells_path.write_bytes(canonical_release_bytes(cells))

    published_path = release_dir / "release.json"
    published = json.loads(published_path.read_text(encoding="utf-8"))
    published["cells"] = cells
    published_path.write_bytes(canonical_release_bytes(published))


@pytest.mark.parametrize("release_dir", RELEASES, ids=lambda path: path.name)
def test_ac1_replays_every_committed_release_offline_and_read_only(
    release_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("QVERIS_API_KEY", raising=False)
    monkeypatch.delenv("WIND_API_KEY", raising=False)

    def reject_network(*args: object, **kwargs: object) -> None:
        raise AssertionError("offline release replay attempted a network request")

    original_open = builtins.open
    original_path_open = Path.open

    def read_only_open(file: object, mode: str = "r", *args: object, **kwargs: object):
        if any(flag in mode for flag in "wax+"):
            raise AssertionError("offline release replay attempted a file write")
        return original_open(file, mode, *args, **kwargs)

    def read_only_path_open(
        path: Path, mode: str = "r", *args: object, **kwargs: object
    ):
        if any(flag in mode for flag in "wax+"):
            raise AssertionError("offline release replay attempted a file write")
        return original_path_open(path, mode, *args, **kwargs)

    monkeypatch.setattr(httpx.Client, "request", reject_network)
    monkeypatch.setattr(httpx.AsyncClient, "request", reject_network)
    monkeypatch.setattr(socket, "create_connection", reject_network)
    monkeypatch.setattr(socket.socket, "connect", reject_network)
    monkeypatch.setattr(subprocess, "run", reject_network)
    monkeypatch.setattr(subprocess, "Popen", reject_network)
    monkeypatch.setattr(builtins, "open", read_only_open)
    monkeypatch.setattr(Path, "open", read_only_path_open)
    before = _tree_snapshot(release_dir)

    result = RUNNER.invoke(app, ["release", "replay", str(release_dir)])

    assert result.exit_code == 0, f"AC1 replay failed: {result.output}"
    assert f"Internal consistency verified {release_dir.name}" in result.output
    assert "external digest not checked" in result.output
    assert "no provider API calls" in result.output
    assert _tree_snapshot(release_dir) == before, "AC1 replay must be read-only"


def test_ac4_replay_checks_an_external_expected_digest() -> None:
    expected = release_digest((REFERENCE_RELEASE / "release.json").read_bytes())

    accepted = RUNNER.invoke(
        app,
        [
            "release",
            "replay",
            str(REFERENCE_RELEASE),
            "--expected-digest",
            expected,
        ],
    )
    rejected = RUNNER.invoke(
        app,
        [
            "release",
            "replay",
            str(REFERENCE_RELEASE),
            "--expected-digest",
            "sha256:" + "0" * 64,
        ],
    )

    assert accepted.exit_code == 0
    assert "External expected digest matched" in accepted.output
    assert "external digest not checked" not in accepted.output
    assert rejected.exit_code == 1
    assert "published release digest does not match expected digest" in rejected.output


@pytest.mark.parametrize("filename", REQUIRED_FILES)
def test_ac2_replay_fails_closed_when_a_required_file_is_missing(
    filename: str,
    tmp_path: Path,
) -> None:
    release_dir = _copy_release(tmp_path)
    (release_dir / filename).unlink()

    result = RUNNER.invoke(app, ["release", "replay", str(release_dir)])

    assert result.exit_code == 1
    assert f"missing release replay file: {filename}" in result.output
    assert "Traceback" not in result.output


@pytest.mark.parametrize("filename", REQUIRED_FILES)
def test_ac2_replay_rejects_malformed_json(
    filename: str,
    tmp_path: Path,
) -> None:
    release_dir = _copy_release(tmp_path)
    (release_dir / filename).write_text("{", encoding="utf-8")

    result = RUNNER.invoke(app, ["release", "replay", str(release_dir)])

    assert result.exit_code == 1
    assert f"invalid release replay file: {filename}" in result.output
    assert "Traceback" not in result.output
    assert "{" not in result.output


def test_ac2_replay_rejects_a_modified_run_plan_digest(tmp_path: Path) -> None:
    release_dir = _copy_release(tmp_path)
    plan_path = release_dir / "run-plan.json"
    plan_path.write_bytes(plan_path.read_bytes() + b"\n")

    result = RUNNER.invoke(app, ["release", "replay", str(release_dir)])

    assert result.exit_code == 1
    assert "run-plan.json digest does not match release input" in result.output


def test_ac2_replay_rejects_a_run_plan_suite_mismatch(tmp_path: Path) -> None:
    release_dir = _copy_release(tmp_path)
    _rewrite_plan(
        release_dir,
        lambda plan: plan.__setitem__("suite_fingerprint", "f" * 64),
    )

    result = RUNNER.invoke(app, ["release", "replay", str(release_dir)])

    assert result.exit_code == 1
    assert (
        "run-plan.json suite fingerprint does not match release input" in result.output
    )


def test_ac2_replay_rejects_a_run_plan_cell_identity_mismatch(
    tmp_path: Path,
) -> None:
    release_dir = _copy_release(tmp_path)

    def replace_provider(plan: dict[str, Any]) -> None:
        plan["cells"][0]["provider_id"] = "different-provider"

    _rewrite_plan(release_dir, replace_provider)

    result = RUNNER.invoke(app, ["release", "replay", str(release_dir)])

    assert result.exit_code == 1
    assert "run-plan.json cell identity does not match terminal cells" in result.output


def test_ac2_replay_rejects_coordinated_run_key_identity_tampering(
    tmp_path: Path,
) -> None:
    release_dir = _copy_release(tmp_path)

    def replace_plan_case(plan: dict[str, Any]) -> None:
        plan["cells"][0]["case_id"] = "different-case"

    def replace_terminal_case(cells: list[dict[str, Any]]) -> None:
        cells[0]["case_id"] = "different-case"

    _rewrite_plan(release_dir, replace_plan_case)
    _rewrite_cells(release_dir, replace_terminal_case)

    result = RUNNER.invoke(app, ["release", "replay", str(release_dir)])

    assert result.exit_code == 1
    assert "run key does not match its cell identity" in result.output


def test_ac2_replay_rejects_a_suite_id_not_bound_to_run_keys(tmp_path: Path) -> None:
    release_dir = _copy_release(tmp_path)
    _rewrite_plan(
        release_dir,
        lambda plan: plan.__setitem__("suite_id", "different-suite"),
    )

    result = RUNNER.invoke(app, ["release", "replay", str(release_dir)])

    assert result.exit_code == 1
    assert "run key does not match its cell identity" in result.output


def test_ac2_new_release_cannot_bypass_failure_attribution(tmp_path: Path) -> None:
    source = ROOT / "releases/sec-filing-evidence-2026-q3-v3"
    release_dir = _copy_release(tmp_path, source)

    def replace_attribution(cells: list[dict[str, Any]]) -> None:
        target = next(cell for cell in cells if cell["state"] == "provider_negative")
        target["failure_attribution"] = "benchmark_system_error"

    _rewrite_cells(release_dir, replace_attribution)

    result = RUNNER.invoke(app, ["release", "replay", str(release_dir)])

    assert result.exit_code == 1
    assert "provider_negative cells require a provider-side" in result.output


def test_ac2_release_directory_must_match_release_id(tmp_path: Path) -> None:
    release_dir = _copy_release(tmp_path)

    result = RUNNER.invoke(app, ["release", "replay", str(release_dir)])

    assert result.exit_code == 1
    assert "release directory name does not match release ID" in result.output


def test_ac2_replay_rejects_a_modified_published_bundle(tmp_path: Path) -> None:
    release_dir = _copy_release(tmp_path)
    published = release_dir / "release.json"
    published.write_bytes(published.read_bytes() + b"\n")

    result = RUNNER.invoke(app, ["release", "replay", str(release_dir)])

    assert result.exit_code == 1
    assert "rebuilt release does not match release.json" in result.output
