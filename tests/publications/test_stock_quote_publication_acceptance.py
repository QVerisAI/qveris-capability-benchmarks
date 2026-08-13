from __future__ import annotations

import json
import shutil
from pathlib import Path

import httpx
import pytest
from typer.testing import CliRunner

from qveris_bench.cap_packs.stock_quote_family.publication_selection import (
    build_stock_quote_selection_snapshot,
)
from qveris_bench.cli import app

ROOT = Path(__file__).resolve().parents[2]
PUBLICATION = ROOT / "docs/guides/capability-seo/stock-quote-api-test"
PACKAGE = PUBLICATION / "manifest.yaml"
RUNNER = CliRunner()


def test_ac1_snapshot_is_release_derived_and_reports_no_winner() -> None:
    built = build_stock_quote_selection_snapshot(
        PUBLICATION / "selection-input.yaml", ROOT
    )
    assert built.json_bytes == (PUBLICATION / "selection-snapshot.json").read_bytes()
    assert len(built.snapshot.rows) == 2
    for row in built.snapshot.rows:
        results = {result.case_id: result for result in row.case_results}
        assert results["invalid-stock"].passed_rounds == 3
        assert all(
            result.passed_rounds == 0
            for case_id, result in results.items()
            if case_id != "invalid-stock"
        )
        assert row.qualified is False


def test_ac2_stock_quote_package_reproduces_offline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("QVERIS_API_KEY", raising=False)

    def reject_network(*args: object, **kwargs: object) -> None:
        raise AssertionError("publication reproduction attempted network access")

    monkeypatch.setattr(httpx.Client, "request", reject_network)
    monkeypatch.setattr(httpx.AsyncClient, "request", reject_network)
    result = RUNNER.invoke(app, ["publication", "reproduce", "--package", str(PACKAGE)])
    assert result.exit_code == 0, result.output
    report = json.loads(result.output)
    assert report["package_id"] == "stock-quote-api-test-2026-08-13"
    assert report["release_count"] == 1
    assert report["status"] == "verified"


def _copy_repository(tmp_path: Path) -> Path:
    copied = tmp_path / "repository"
    copied.mkdir()
    shutil.copy2(ROOT / "pyproject.toml", copied / "pyproject.toml")
    for relative in (
        "cap_packs/stock_quote_family",
        "docs/guides/capability-seo/stock-quote-api-test",
        "evidence/stock-quote-family-2026-q3-v1",
        "providers",
        "releases/stock-quote-family-2026-q3-v1",
    ):
        source = ROOT / relative
        target = copied / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(source, target)
    article = copied / "docs/guides/stock-quote-api-test.md"
    article.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / "docs/guides/stock-quote-api-test.md", article)
    return copied


@pytest.mark.parametrize(
    ("relative", "old", "new", "message"),
    [
        (
            "docs/guides/stock-quote-api-test.md",
            b"Neither tested Access Path qualified",
            b"Both tested Access Paths qualified",
            "article verdict drifted",
        ),
        (
            "docs/guides/stock-quote-api-test.md",
            b"0/3",
            b"3/3",
            "article result drifted",
        ),
        (
            "docs/guides/stock-quote-api-test.md",
            b"stale timestamp",
            b"fastest response",
            "article reason drifted",
        ),
        (
            "docs/guides/stock-quote-api-test.md",
            b"Free plan with 60 API calls per minute",
            b"Free plan with 600 API calls per minute",
            "article pricing drifted",
        ),
        (
            "docs/guides/stock-quote-api-test.md",
            b"https://finnhub.io/pricing",
            b"https://evil.example/pricing",
            "article external links differ from the allowlist",
        ),
        (
            "docs/guides/capability-seo/stock-quote-api-test/selection-snapshot.json",
            b'"qualified": false',
            b'"qualified": true',
            "selection snapshot differs",
        ),
        (
            "docs/guides/capability-seo/stock-quote-api-test/manifest.yaml",
            b"public_evidence_records: 30",
            b"public_evidence_records: 300",
            "release public evidence count mismatch",
        ),
        (
            "docs/guides/capability-seo/stock-quote-api-test/manifest.yaml",
            b"rounds_per_cell: 3",
            b"rounds_per_cell: 9",
            "release round count mismatch",
        ),
        (
            "docs/guides/capability-seo/stock-quote-api-test/manifest.yaml",
            b"release_sections: [release]",
            b"release_sections: [release, extra]",
            "missing publication release section",
        ),
        (
            "docs/guides/capability-seo/stock-quote-api-test/charts/stock-quote-outcomes.png",
            b"PNG",
            b"BAD",
            "committed chart digest mismatch",
        ),
    ],
)
def test_ac3_material_drift_fails_closed(
    tmp_path: Path,
    relative: str,
    old: bytes,
    new: bytes,
    message: str,
) -> None:
    repository = _copy_repository(tmp_path)
    target = repository / relative
    content = target.read_bytes()
    assert old in content
    target.write_bytes(content.replace(old, new, 1))
    package = (
        repository / "docs/guides/capability-seo/stock-quote-api-test/manifest.yaml"
    )

    result = RUNNER.invoke(app, ["publication", "reproduce", "--package", str(package)])

    assert result.exit_code == 1
    assert message in result.output
