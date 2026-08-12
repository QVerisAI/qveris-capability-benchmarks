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
        "cap_packs/dividend_events",
        "docs/guides/capability-seo/best-dividend-apis",
        "evidence/dividend-events-2026-q3-v1",
        "evidence/dividend-events-market-coverage-2026-q3-v1",
        "providers",
        "releases/dividend-events-2026-q3-v1",
        "releases/dividend-events-market-coverage-2026-q3-v1",
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
            "docs/guides/capability-seo/best-dividend-apis/manifest.yaml",
            (
                b"digest: sha256:7be689447caf0574b03e8ed6f9e31a7e3d607856d5780eac"
                b"2ca0b5e61d7cef23"
            ),
            b"digest: sha256:" + b"0" * 64,
            "qveris_list_pricing digest mismatch",
        ),
        (
            "docs/guides/capability-seo/best-dividend-apis/manifest.yaml",
            (
                b"    - docs/guides/capability-seo/best-dividend-apis/charts/"
                b"dividend-market-coverage.png\n"
            ),
            b"",
            "declared, committed, and generated chart sets must match",
        ),
        (
            "docs/guides/best-dividend-apis.md",
            b"We made 102 live calls",
            b"We made 999 live calls",
            "article call total drifted",
        ),
        (
            "docs/guides/best-dividend-apis.md",
            b"**Sample passed:** both the AAPL sample",
            b"**Sample did not pass:** both the AAPL sample",
            "baseline outcome drifted",
        ),
        (
            "docs/guides/best-dividend-apis.md",
            b"EODHD passed 7 markets",
            b"EODHD passed 99 markets",
            "quick recommendation market count drifted",
        ),
        (
            "docs/guides/best-dividend-apis.md",
            b"https://qveris.ai/providers/hangseng_polysource",
            b"https://qveris.ai/providers/alphavantage",
            "QVeris CTA drifted",
        ),
        (
            "docs/guides/best-dividend-apis.md",
            b"| Alpha Vantage (QVeris) | 3/3 |",
            b"| Alpha Vantage (QVeris) | 0/3 |",
            "Agent facts drifted",
        ),
        (
            "docs/guides/capability-seo/best-dividend-apis/manifest.yaml",
            b"planned_cells: 120",
            b"planned_cells: 999",
            "market_coverage_release planned cell count mismatch",
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


def test_ac5_release_sections_must_be_unique(tmp_path: Path) -> None:
    repository = _copy_publication_repository(tmp_path)
    package = repository / "docs/guides/capability-seo/best-dividend-apis/manifest.yaml"
    content = package.read_text(encoding="utf-8")
    package.write_text(
        content.replace(
            "release_sections: [release, market_coverage_release]",
            "release_sections: [release, release, market_coverage_release]",
        ),
        encoding="utf-8",
    )

    with pytest.raises(
        PublicationReproductionError,
        match="publication release sections must be unique",
    ):
        reproduce_publication_package(package)
