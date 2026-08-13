from __future__ import annotations

import hashlib
import json
import os
import shutil
import socket
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
        "harbor_catalog",
        "providers",
        "releases/dividend-events-2026-q3-v5",
        "releases/dividend-events-market-coverage-2026-q3-v5",
        "src/qveris_bench/cap_packs/dividend_events/publication.py",
        "src/qveris_bench/cap_packs/dividend_events/selection_charts.py",
    ):
        source = ROOT / relative
        target = copied / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if source.is_dir():
            shutil.copytree(source, target)
        else:
            shutil.copy2(source, target)
    article = copied / "docs/guides/best-dividend-apis.md"
    article.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / "docs/guides/best-dividend-apis.md", article)
    return copied


def _repository_snapshot() -> dict[str, bytes]:
    paths = (
        ROOT / "docs/guides/best-dividend-apis.md",
        PUBLICATION_DIR / "selection-snapshot.json",
        PUBLICATION_DIR / "article-facts.json",
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
    monkeypatch.setattr(socket, "create_connection", reject_network)
    monkeypatch.setattr(socket.socket, "connect", reject_network)
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
            "releases/dividend-events-2026-q3-v5/release.json",
            b'"release_id": "dividend-events-2026-q3-v5"',
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
            "article facts drifted",
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
            "quick recommendation drifted",
        ),
        (
            "docs/guides/best-dividend-apis.md",
            b"start by reproducing Alpha Vantage, Twelve Data, EODHD, or Massive",
            b"start by reproducing iFinD",
            "quick recommendation drifted",
        ),
        (
            "docs/guides/best-dividend-apis.md",
            b"Twelve Data had the lowest median latency",
            b"EODHD had the lowest median latency",
            "latency ranking drifted",
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
        (
            "docs/guides/capability-seo/best-dividend-apis/manifest.yaml",
            b'edition: "2026-08-12"',
            b'edition: "2025-01-01"',
            "publication edition mismatch",
        ),
        (
            "docs/guides/capability-seo/best-dividend-apis/manifest.yaml",
            b"  rounds_per_cell: 2",
            b"  rounds_per_cell: 999",
            "market_coverage_release round count mismatch",
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


def test_ac5_dividend_adapter_rejects_an_extra_release(tmp_path: Path) -> None:
    repository = _copy_publication_repository(tmp_path)
    package = repository / "docs/guides/capability-seo/best-dividend-apis/manifest.yaml"
    content = package.read_text(encoding="utf-8")
    package.write_text(
        content.replace(
            "release_sections: [release, market_coverage_release]",
            "release_sections: [release, market_coverage_release, extra_release]",
        ).replace(
            "search_intent:",
            (
                "extra_release:"
                "\n  directory: releases/dividend-events-2026-q3-v5"
                "\n  digest: "
                "sha256:a24c398a6a6dcae35c5fac0b53b162aefb4253b34d8689416093751e5cfabe2a"
                "\nsearch_intent:"
            ),
        ),
        encoding="utf-8",
    )

    with pytest.raises(
        PublicationReproductionError,
        match="publication release identities must be unique",
    ):
        reproduce_publication_package(package)


def test_ac5_selection_input_rejects_a_nested_path_escape(tmp_path: Path) -> None:
    repository = _copy_publication_repository(tmp_path)
    selection_input = (
        repository
        / "docs/guides/capability-seo/best-dividend-apis/selection-snapshot.yaml"
    )
    content = selection_input.read_text(encoding="utf-8")
    selection_input.write_text(
        content.replace(
            "suite: cap_packs/dividend_events/suite.yaml",
            "suite: ../../outside.yaml",
        ),
        encoding="utf-8",
    )
    package = repository / "docs/guides/capability-seo/best-dividend-apis/manifest.yaml"

    with pytest.raises(
        PublicationReproductionError,
        match="path must stay inside the repository",
    ):
        reproduce_publication_package(package)


@pytest.mark.parametrize(
    "release_id",
    [
        "dividend-events-2026-q3-v5",
        "dividend-events-market-coverage-2026-q3-v5",
    ],
)
def test_ac6_publication_requires_every_public_evidence_manifest(
    tmp_path: Path,
    release_id: str,
) -> None:
    repository = _copy_publication_repository(tmp_path)
    (repository / "releases" / release_id / "public-evidence-manifest.json").unlink()

    with pytest.raises(
        PublicationReproductionError,
        match="public evidence manifest is required",
    ):
        reproduce_publication_package(
            repository / "docs/guides/capability-seo/best-dividend-apis/manifest.yaml"
        )


def test_ac6_unreleased_evidence_cannot_change_agent_facts(tmp_path: Path) -> None:
    repository = _copy_publication_repository(tmp_path)
    evidence_dir = repository / "evidence/dividend-events-2026-q3-v1"
    source = evidence_dir / "alpha-vantage-aapl-dividends-round-1-terminal.json"
    shutil.copy2(source, evidence_dir / "unreleased-alpha-terminal.json")
    article = repository / "docs/guides/best-dividend-apis.md"
    article.write_text(
        article.read_text(encoding="utf-8").replace(
            "| Alpha Vantage (QVeris) | 3/3 |",
            "| Alpha Vantage (QVeris) | 4/4 |",
        ),
        encoding="utf-8",
    )

    with pytest.raises(
        PublicationReproductionError,
        match="public evidence file set differs|Agent facts drifted",
    ):
        reproduce_publication_package(
            repository / "docs/guides/capability-seo/best-dividend-apis/manifest.yaml"
        )


def test_ac6_provider_access_path_identity_is_exact(tmp_path: Path) -> None:
    repository = _copy_publication_repository(tmp_path)
    article = repository / "docs/guides/best-dividend-apis.md"
    text = article.read_text(encoding="utf-8")
    for old, new in (
        ("] (QVeris) · [Try it in QVeris]", "] (Native MCP) · [Try it in QVeris]"),
        ("[Alpha Vantage / QVeris]", "[Alpha Vantage / Native MCP]"),
        ("| Alpha Vantage / QVeris |", "| Alpha Vantage / Native MCP |"),
        ("| Alpha Vantage (QVeris) |", "| Alpha Vantage (Native MCP) |"),
    ):
        if old.startswith("]"):
            prefix = (
                "[Alpha Vantage](https://www.alphavantage.co/documentation/#dividends)"
            )
            text = text.replace(prefix + old, prefix + new, 1)
        else:
            text = text.replace(old, new, 1)
    article.write_text(text, encoding="utf-8")

    with pytest.raises(
        PublicationReproductionError,
        match="Provider and Access Path identity drifted",
    ):
        reproduce_publication_package(
            repository / "docs/guides/capability-seo/best-dividend-apis/manifest.yaml"
        )


@pytest.mark.parametrize(
    ("old", "new"),
    [
        (
            "Each applicable Access Path had one positive security sample and one "
            "invalid-symbol negative control, each repeated three times: "
            "36 live calls.",
            "Each applicable Access Path had one positive security sample and one "
            "invalid-symbol negative control, each repeated three times: "
            "999 live calls.",
        ),
        (
            "The market Release contains 120 planned test cells. All 66 applicable "
            "cells have sanitized public evidence, while the other 54 retain an "
            "explicit not-applicable reason.",
            "The market Release contains 999 planned test cells. All 1 applicable "
            "cells have sanitized public evidence, while the other 998 retain an "
            "explicit not-applicable reason.",
        ),
        (
            "`sha256:9c11f7c920c0c6bd774a012b326c40e748142ff9f9c11df060850f8a1db8aead`",
            "`sha256:" + "0" * 64 + "`",
        ),
    ],
)
def test_ac6_every_material_release_claim_is_bound(
    tmp_path: Path,
    old: str,
    new: str,
) -> None:
    repository = _copy_publication_repository(tmp_path)
    article = repository / "docs/guides/best-dividend-apis.md"
    text = article.read_text(encoding="utf-8")
    assert old in text
    article.write_text(text.replace(old, new, 1), encoding="utf-8")

    with pytest.raises(PublicationReproductionError, match="article facts drifted"):
        reproduce_publication_package(
            repository / "docs/guides/capability-seo/best-dividend-apis/manifest.yaml"
        )


def test_ac6_chart_pixels_cannot_be_replaced_with_coordinated_digests(
    tmp_path: Path,
) -> None:
    repository = _copy_publication_repository(tmp_path)
    publication = repository / "docs/guides/capability-seo/best-dividend-apis"
    runtime = publication / "charts/dividend-runtime-tradeoff.png"
    market = publication / "charts/dividend-market-coverage.png"
    market.write_bytes(runtime.read_bytes())
    chart_manifest = publication / "charts/selection-charts-manifest.json"
    chart_document = json.loads(chart_manifest.read_text(encoding="utf-8"))
    chart_document["charts"][market.name] = (
        "sha256:" + hashlib.sha256(market.read_bytes()).hexdigest()
    )
    chart_manifest.write_text(
        json.dumps(chart_document, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    package = publication / "manifest.yaml"
    package_text = package.read_text(encoding="utf-8")
    package.write_text(
        package_text.replace(
            "selection_charts_manifest_digest: sha256:"
            "1c35175fdcc204dc5caeec95097c2b715745c4b08cdc13bf58c343301c307344",
            "selection_charts_manifest_digest: sha256:"
            + hashlib.sha256(chart_manifest.read_bytes()).hexdigest(),
        ),
        encoding="utf-8",
    )

    with pytest.raises(
        PublicationReproductionError,
        match="canonical chart pixels differ",
    ):
        reproduce_publication_package(package)


def test_ac6_adapter_source_change_requires_a_new_digest(tmp_path: Path) -> None:
    repository = _copy_publication_repository(tmp_path)
    source = (
        repository / "src/qveris_bench/cap_packs/dividend_events/selection_charts.py"
    )
    source.write_text(source.read_text(encoding="utf-8") + "\n", encoding="utf-8")

    with pytest.raises(
        PublicationReproductionError,
        match="publication adapter digest mismatch",
    ):
        reproduce_publication_package(
            repository / "docs/guides/capability-seo/best-dividend-apis/manifest.yaml"
        )


def test_ac6_malformed_publication_artifact_has_a_stable_error(tmp_path: Path) -> None:
    repository = _copy_publication_repository(tmp_path)
    snapshot = (
        repository
        / "docs/guides/capability-seo/best-dividend-apis/selection-snapshot.json"
    )
    snapshot.write_text("{", encoding="utf-8")

    with pytest.raises(
        PublicationReproductionError,
        match="selection snapshot differs",
    ):
        reproduce_publication_package(
            repository / "docs/guides/capability-seo/best-dividend-apis/manifest.yaml"
        )
