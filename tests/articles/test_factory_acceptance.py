# ruff: noqa: E501

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from qveris_bench.articles.factory import (
    ArticleBuildError,
    build_article_package,
)
from qveris_bench.cli import app

ROOT = Path(__file__).resolve().parents[2]
SNAPSHOT = (
    ROOT / "docs/guides/capability-seo/best-dividend-apis/selection-snapshot.json"
)


def _profile(path: Path) -> Path:
    path.write_text(
        """title: Best Dividend Event APIs for Developers
meta_description: Evidence-backed comparison of dividend event access paths, with measured latency, QVeris list credits, markets, and Agent integration signals.
cap_label: Dividend Event
scope: Historical dividend-event retrieval through the tested QVeris and Native Access Paths.
provider_links:
  alpha-vantage:
    name: Alpha Vantage
    official: https://www.alphavantage.co/
    qveris: https://qveris.ai/providers/alphavantage
  eodhd:
    name: EODHD
    official: https://eodhd.com/
    qveris: https://qveris.ai/providers/eodhd
  hangseng:
    name: Hang Seng
    official: https://www.gildata.com/
    qveris: https://qveris.ai/providers/hangseng_polysource
  ifind:
    name: iFinD
    official: https://quantapi.51ifind.com/
  massive-stocks:
    name: Massive
    official: https://massive.io/
    qveris: https://qveris.ai/providers/massive_stocks
  twelve-data:
    name: Twelve Data
    official: https://twelvedata.com/
    qveris: https://qveris.ai/providers/twelvedata
""",
        encoding="utf-8",
    )
    return path


def test_ac1_builds_complete_english_article_and_two_snapshot_bound_charts(
    tmp_path: Path,
) -> None:
    output = tmp_path / "publication"
    result = build_article_package(
        SNAPSHOT,
        _profile(tmp_path / "profile.yaml"),
        output,
    )

    article = result.article.read_text(encoding="utf-8")
    assert article.startswith("# Best Dividend Event APIs for Developers")
    for heading in (
        "## Quick recommendations",
        "## Comparison table",
        "## Market coverage",
        "## Latency and QVeris list-price trade-off",
        "## Agent integration notes",
        "## How we tested, reproduce, and contribute",
        "## Limitations and FAQ",
    ):
        assert heading in article
    assert "Alpha Vantage · QVeris connector" in article
    assert "iFinD · Native MCP" in article
    assert "Evidence insufficient" in article
    assert "| Provider × Access Path |" in article
    assert result.runtime_chart.is_file()
    assert result.market_chart.is_file()
    manifest = json.loads(result.manifest.read_text(encoding="utf-8"))
    assert manifest["input_digests"]["selection_snapshot"].startswith("sha256:")
    assert set(manifest["charts"]) == {
        result.runtime_chart.name,
        result.market_chart.name,
    }


def test_ac3_refuses_to_publish_when_no_runtime_chart_has_release_backed_data(
    tmp_path: Path,
) -> None:
    snapshot = json.loads(SNAPSHOT.read_text())
    for row in snapshot["rows"]:
        row["gateway_metrics"] = {
            "state": "evidence_insufficient",
            "latency_sample_size": 0,
            "latency_min_ms": None,
            "latency_median_ms": None,
            "latency_max_ms": None,
            "cost_sample_size": 0,
            "median_credits": None,
            "evidence_refs": [],
            "latency_evidence_refs": [],
            "cost_evidence_refs": [],
        }
    invalid_snapshot = tmp_path / "selection-snapshot.json"
    invalid_snapshot.write_text(json.dumps(snapshot), encoding="utf-8")

    with pytest.raises(ArticleBuildError, match="runtime chart"):
        build_article_package(
            invalid_snapshot,
            _profile(tmp_path / "profile.yaml"),
            tmp_path / "publication",
        )


def test_ac6_cli_builds_the_offline_article_package(tmp_path: Path) -> None:
    result = CliRunner().invoke(
        app,
        [
            "article",
            "build",
            "--selection-snapshot",
            str(SNAPSHOT),
            "--profile",
            str(_profile(tmp_path / "profile.yaml")),
            "--output-dir",
            str(tmp_path / "publication"),
        ],
    )

    assert result.exit_code == 0, result.output
    assert "Built article package" in result.output
    assert (tmp_path / "publication/article.md").is_file()
