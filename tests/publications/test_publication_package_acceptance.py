from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import httpx
import pytest
from typer.testing import CliRunner

from qveris_bench.cli import app
from qveris_bench.publications.service import (
    PublicationReproductionError,
    reproduce_publication_package,
    resolve_repository_path,
)

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT / "docs/guides/capability-seo/best-dividend-apis/manifest.yaml"
PUBLICATION_DIR = PACKAGE.parent
RUNNER = CliRunner()


def _copy_publication_repository(tmp_path: Path) -> Path:
    copied = tmp_path / "repository"
    copied.mkdir()
    shutil.copy2(ROOT / "pyproject.toml", copied / "pyproject.toml")
    for relative in (
        "assets/fonts",
        "cap_packs/dividend_events",
        "docs/guides/capability-seo/best-dividend-apis",
        "evidence/dividend-events-2026-q3-v1",
        "evidence/dividend-events-market-coverage-2026-q3-v1",
        "providers",
        "releases/dividend-events-2026-q3-v1",
        "releases/dividend-events-market-coverage-2026-q3-v1",
        "scripts",
    ):
        source = ROOT / relative
        target = copied / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(source, target)
    article = copied / "docs/guides/best-dividend-apis.md"
    article.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / "docs/guides/best-dividend-apis.md", article)
    return copied


def _repository_snapshot() -> dict[str, bytes]:
    paths = (
        ROOT / "docs/guides/best-dividend-apis.md",
        PUBLICATION_DIR / "selection-snapshot.json",
        PUBLICATION_DIR / "charts/selection-charts-manifest.json",
        PUBLICATION_DIR / "charts/dividend-runtime-tradeoff.png",
        PUBLICATION_DIR / "charts/dividend-market-coverage.png",
    )
    return {str(path.relative_to(ROOT)): path.read_bytes() for path in paths}


def test_ac1_dividend_publication_reproduces_offline_and_read_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("QVERIS_API_KEY", raising=False)
    monkeypatch.delenv("IFIND_MCP_API_KEY", raising=False)

    def reject_network(*args: object, **kwargs: object) -> None:
        raise AssertionError("publication reproduction attempted a network request")

    monkeypatch.setattr(httpx.Client, "request", reject_network)
    monkeypatch.setattr(httpx.AsyncClient, "request", reject_network)
    before = _repository_snapshot()

    result = RUNNER.invoke(
        app,
        ["publication", "reproduce", "--package", str(PACKAGE)],
    )

    assert result.exit_code == 0, result.output
    report = json.loads(result.output)
    assert report["package_id"] == "best-dividend-apis-2026-08-12"
    assert report["status"] == "verified"
    assert report["release_count"] == 2
    assert report["checks"] == [
        "releases",
        "selection_snapshot",
        "charts",
        "article_facts",
        "links",
    ]
    assert _repository_snapshot() == before


def test_ac2_installed_cli_reproduces_the_dividend_publication() -> None:
    executable = shutil.which("qveris-bench")
    assert executable is not None, "installed qveris-bench entry point is required"

    result = subprocess.run(
        [executable, "publication", "reproduce", "--package", str(PACKAGE)],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        env={"PATH": str(Path(executable).parent)},
    )

    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["status"] == "verified"


@pytest.mark.parametrize("path", ["../../outside", "/tmp/outside"])
def test_ac3_publication_rejects_a_path_outside_the_repository(path: str) -> None:
    with pytest.raises(
        PublicationReproductionError,
        match="path must stay inside the repository",
    ):
        resolve_repository_path(ROOT, path)


def test_ac3_publication_rejects_a_symlink_escape(tmp_path: Path) -> None:
    outside = tmp_path / "outside.json"
    outside.write_text("{}", encoding="utf-8")
    link = ROOT / ".publication-symlink-test"
    try:
        os.symlink(outside, link)
        with pytest.raises(
            PublicationReproductionError,
            match="path must stay inside the repository",
        ):
            resolve_repository_path(ROOT, link.name)
    finally:
        link.unlink(missing_ok=True)


@pytest.mark.parametrize(
    ("relative_path", "old", "new", "message"),
    [
        (
            "releases/dividend-events-2026-q3-v1/release.json",
            b'"release_id": "dividend-events-2026-q3-v1"',
            b'"release_id": "tampered-release"',
            "release reproduction failed",
        ),
        (
            "docs/guides/capability-seo/best-dividend-apis/selection-snapshot.json",
            b'"edition": "2026-08-12"',
            b'"edition": "2026-08-13"',
            "selection snapshot differs",
        ),
        (
            "docs/guides/capability-seo/best-dividend-apis/charts/selection-charts-manifest.json",
            b'"rendered_at": "2026-08-12"',
            b'"rendered_at": "2026-08-13"',
            "selection chart manifest digest mismatch",
        ),
        (
            "docs/guides/capability-seo/best-dividend-apis/charts/dividend-market-coverage.png",
            b"PNG",
            b"BAD",
            "committed chart digest mismatch",
        ),
        (
            "docs/guides/capability-seo/best-dividend-apis/manifest.yaml",
            b"adapter_id: dividend-events-v1",
            b"adapter_id: missing-adapter",
            "publication adapter must resolve exactly once",
        ),
        (
            "docs/guides/best-dividend-apis.md",
            b"We made 102 live calls",
            b"We made 999 live calls",
            "article call total drifted",
        ),
    ],
)
def test_ac4_coordinated_publication_drift_fails_closed(
    tmp_path: Path,
    relative_path: str,
    old: bytes,
    new: bytes,
    message: str,
) -> None:
    repository = _copy_publication_repository(tmp_path)
    target = repository / relative_path
    content = target.read_bytes()
    assert old in content
    target.write_bytes(content.replace(old, new, 1))
    package = repository / "docs/guides/capability-seo/best-dividend-apis/manifest.yaml"

    with pytest.raises(PublicationReproductionError, match=message):
        reproduce_publication_package(package)


def test_ac5_external_package_digest_detects_manifest_drift() -> None:
    with pytest.raises(
        PublicationReproductionError,
        match="package digest does not match expected digest",
    ):
        reproduce_publication_package(
            PACKAGE,
            expected_package_digest="sha256:" + "0" * 64,
        )
