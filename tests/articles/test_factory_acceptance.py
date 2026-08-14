# ruff: noqa: E501

from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path

import pytest
from PIL import Image
from typer.testing import CliRunner

from qveris_bench.articles.factory import (
    ArticleBuildError,
    _load_snapshot,
    _market_rows,
    _render_market_chart,
    _same_pixels,
    build_article_package,
    reproduce_article_package,
)
from qveris_bench.cli import app

ROOT = Path(__file__).resolve().parents[2]
SNAPSHOT = (
    ROOT / "docs/guides/capability-seo/best-dividend-apis/selection-snapshot.json"
)
CORPORATE_ACTIONS_V2_SNAPSHOT = (
    ROOT
    / "selection_snapshots/corporate-actions-v2-publication/selection-snapshot.json"
)
CORPORATE_ACTIONS_PROFILE = (
    ROOT
    / "docs/guides/capability-seo/best-corporate-actions-apis/publication-profile.yaml"
)


def _profile(path: Path) -> Path:
    path.write_text(
        """title: Best Dividend Event APIs for Developers
meta_description: Evidence-backed comparison of dividend event access paths, with measured latency, QVeris list credits, markets, and Agent integration signals.
cap_label: Dividend Event
scope: Historical dividend-event retrieval through the tested QVeris and Native Access Paths.
allowed_links:
  - https://www.alphavantage.co/
  - https://qveris.ai/providers/alphavantage
  - https://eodhd.com/
  - https://qveris.ai/providers/eodhd
  - https://www.gildata.com/
  - https://www.gildata.com/products/core-data.html
  - https://qveris.ai/providers/hangseng_polysource
  - https://quantapi.51ifind.com/
  - https://massive.io/
  - https://qveris.ai/providers/massive_stocks
  - https://twelvedata.com/
  - https://qveris.ai/providers/twelvedata
  - https://www.alphavantage.co/premium/
  - https://eodhd.com/pricing
  - https://massive.com/pricing?product=stocks
  - https://mcp.51ifind.com/?syncCookieTimes=1#/pricing
  - https://twelvedata.com/pricing
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


def test_corporate_actions_v2_article_projects_nine_markets_and_all_live_evidence(
    tmp_path: Path,
) -> None:
    result = build_article_package(
        CORPORATE_ACTIONS_V2_SNAPSHOT,
        CORPORATE_ACTIONS_PROFILE,
        tmp_path / "publication",
    )

    article = result.article.read_text(encoding="utf-8")
    assert "nine representative markets" in article
    assert "72 release-backed live calls" in article
    assert "0/2 Evidence insufficient" in article
    assert "<package-manifest>" not in article
    assert (
        "--package docs/guides/capability-seo/best-corporate-actions-apis/manifest.yaml"
        in article
    )
    assert "--expected-package-digest <published-digest>" in article
    assert result.market_chart.is_file()

    command = re.search(r"Reproduce the package offline with `(.*?)`", article)
    assert command is not None
    attestation = json.loads(
        (
            ROOT
            / "docs/guides/publication-attestations/best-corporate-actions-apis-2026-08-14-v2.json"
        ).read_text(encoding="utf-8")
    )
    executable = command.group(1).replace(
        "<published-digest>", attestation["package_digest"]
    )
    reproduced = subprocess.run(
        executable,
        cwd=ROOT,
        shell=True,
        check=False,
        capture_output=True,
        text=True,
        env={**os.environ, "UV_CACHE_DIR": str(tmp_path / "uv-cache")},
    )
    assert reproduced.returncode == 0, reproduced.stderr


def test_ac1_market_chart_omits_redundant_access_path_type(tmp_path: Path) -> None:
    rows = tuple(
        sorted(
            _load_snapshot(CORPORATE_ACTIONS_V2_SNAPSHOT).rows,
            key=lambda row: (row.provider_name, row.access_path_id),
        )
    )
    chart = tmp_path / "market-coverage.svg"

    _render_market_chart(
        _market_rows(rows),
        {row.provider_id: row.provider_name for row in rows},
        "Corporate Actions",
        chart,
    )

    rendered = chart.read_text(encoding="utf-8")
    assert "<!-- Alpha Vantage -->" in rendered, "AC1: Provider label is missing"
    assert "QVeris connector" not in rendered, "AC1: repeated path type remains"


def test_ac2_market_chart_distinguishes_multiple_paths_for_one_provider(
    tmp_path: Path,
) -> None:
    row = _market_rows((_load_snapshot(CORPORATE_ACTIONS_V2_SNAPSHOT).rows[0],))[0]
    alternate = row.model_copy(update={"access_path_id": "alternate-qveris-path"})
    chart = tmp_path / "market-coverage.svg"

    _render_market_chart(
        (row, alternate),
        {row.provider_id: row.provider_name},
        "Corporate Actions",
        chart,
    )

    rendered = chart.read_text(encoding="utf-8")
    assert row.access_path_id in rendered, "AC2: original Access Path is ambiguous"
    assert alternate.access_path_id in rendered, (
        "AC2: alternate Access Path is ambiguous"
    )


def test_ac4_article_skill_requires_non_redundant_chart_labels() -> None:
    blueprint = (
        ROOT / ".agents/skills/cap-article-writer/references/article-blueprint.md"
    ).read_text(encoding="utf-8")

    assert "omit a repeated Access Path type" in blueprint, (
        "AC4: chart-label guidance is missing from the Article Writer Skill"
    )
    assert "retain enough Access Path identity" in blueprint, (
        "AC4: duplicate Provider rows could become ambiguous"
    )


def test_ac3_chart_pixel_comparison_rejects_rgb_tampering(tmp_path: Path) -> None:
    expected = tmp_path / "expected.png"
    tampered = tmp_path / "tampered.png"
    Image.new("RGBA", (1, 1), (0, 0, 0, 255)).save(expected)
    Image.new("RGBA", (1, 1), (255, 0, 255, 255)).save(tampered)

    assert not _same_pixels(expected, tampered), (
        "AC3: an RGB-only chart mutation was accepted"
    )


def test_ac3_chart_pixel_comparison_rejects_alpha_tampering(tmp_path: Path) -> None:
    expected = tmp_path / "expected.png"
    tampered = tmp_path / "tampered.png"
    Image.new("RGBA", (1, 1), (255, 0, 0, 255)).save(expected)
    Image.new("RGBA", (1, 1), (255, 0, 0, 0)).save(tampered)

    assert not _same_pixels(expected, tampered), (
        "AC3: an alpha-only chart mutation was accepted"
    )


def test_corporate_actions_skill_article_matches_golden_reader_structure(
    tmp_path: Path,
) -> None:
    package = ROOT / "docs/guides/capability-seo/best-corporate-actions-apis"
    result = build_article_package(
        CORPORATE_ACTIONS_V2_SNAPSHOT,
        CORPORATE_ACTIONS_PROFILE,
        tmp_path / "publication",
        writer_input_path=package / "writer-input.json",
        editorial_path=package / "editorial.json",
    )

    article = result.article.read_text(encoding="utf-8")
    for heading in (
        "## Contents",
        "## Results at a glance",
        "## How developers should choose",
        "## Evidence and Provider differences",
        "### Provider-by-Provider analysis",
        "## What AI Agent builders should verify",
        "## Method, reproduction, and contribution",
        "### No key required: reproduce the publication offline",
        "### With a configured key: start a new live evidence run",
        "### How Providers and developers can participate",
        "## Limitations, disclosures, and corrections",
        "## FAQ",
    ):
        assert heading in article
    assert article.count("**Evidence-backed shortlist:**") >= 4
    assert article.count("#### ") == 4
    assert article.count("### ") >= 14
    assert article.count("[![") == 2
    assert len(article.split()) >= 2200
    assert "qveris-bench cap run" not in article
    assert "gh workflow run live-corporate-actions-baseline-e2e.yml" in article
    assert "outside the checkout" in article


def test_skill_article_build_rejects_tampered_writer_input(tmp_path: Path) -> None:
    package = ROOT / "docs/guides/capability-seo/best-corporate-actions-apis"
    writer_input = json.loads((package / "writer-input.json").read_text())
    writer_input["public_observations"][0]["facts"]["ratio"] = 999
    tampered = tmp_path / "writer-input.json"
    tampered.write_text(json.dumps(writer_input), encoding="utf-8")

    with pytest.raises(ArticleBuildError, match="release-backed public evidence"):
        build_article_package(
            CORPORATE_ACTIONS_V2_SNAPSHOT,
            CORPORATE_ACTIONS_PROFILE,
            tmp_path / "publication",
            writer_input_path=tampered,
            editorial_path=package / "editorial.json",
        )


def test_skill_article_prepare_build_round_trip_accepts_copied_snapshot(
    tmp_path: Path,
) -> None:
    package = ROOT / "docs/guides/capability-seo/best-corporate-actions-apis"
    copied_snapshot = tmp_path / "selection-snapshot.json"
    copied_snapshot.write_bytes(CORPORATE_ACTIONS_V2_SNAPSHOT.read_bytes())

    result = build_article_package(
        copied_snapshot,
        CORPORATE_ACTIONS_PROFILE,
        tmp_path / "publication",
        writer_input_path=package / "writer-input.json",
        editorial_path=package / "editorial.json",
    )

    assert result.article.is_file()


def test_article_reproduction_rejects_tampered_editorial_digest(
    tmp_path: Path,
) -> None:
    package = ROOT / "docs/guides/capability-seo/best-corporate-actions-apis"
    output = tmp_path / "publication"
    build_article_package(
        CORPORATE_ACTIONS_V2_SNAPSHOT,
        CORPORATE_ACTIONS_PROFILE,
        output,
        writer_input_path=package / "writer-input.json",
        editorial_path=package / "editorial.json",
    )
    manifest_path = output / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["input_digests"]["editorial"] = "sha256:" + "0" * 64
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ArticleBuildError, match="input digest"):
        reproduce_article_package(
            CORPORATE_ACTIONS_V2_SNAPSHOT,
            CORPORATE_ACTIONS_PROFILE,
            output,
            writer_input_path=package / "writer-input.json",
            editorial_path=package / "editorial.json",
        )


def test_rejects_an_unapproved_profile_link(tmp_path: Path) -> None:
    profile = _profile(tmp_path / "profile.yaml")
    profile.write_text(
        profile.read_text(encoding="utf-8").replace(
            "official: https://www.alphavantage.co/",
            "official: https://unapproved.example/",
        ),
        encoding="utf-8",
    )

    with pytest.raises(ArticleBuildError, match="unapproved link"):
        build_article_package(SNAPSHOT, profile, tmp_path / "publication")


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


def test_ac5_reproduction_rejects_a_tampered_article(tmp_path: Path) -> None:
    output = tmp_path / "publication"
    profile = _profile(tmp_path / "profile.yaml")
    build_article_package(SNAPSHOT, profile, output)
    article = output / "article.md"
    article.write_text(article.read_text(encoding="utf-8") + "\nFalse claim.\n")

    with pytest.raises(ArticleBuildError, match="article artifact differs"):
        reproduce_article_package(SNAPSHOT, profile, output)


def test_ac5_cli_reproduces_the_article_package_offline(tmp_path: Path) -> None:
    output = tmp_path / "publication"
    profile = _profile(tmp_path / "profile.yaml")
    build_article_package(SNAPSHOT, profile, output)

    result = CliRunner().invoke(
        app,
        [
            "article",
            "reproduce",
            "--selection-snapshot",
            str(SNAPSHOT),
            "--profile",
            str(profile),
            "--output-dir",
            str(output),
        ],
    )

    assert result.exit_code == 0, result.output
    assert "Verified article package" in result.output


def test_v2_reproduction_requires_every_chart_digest(tmp_path: Path) -> None:
    from qveris_bench.articles.factory_v2 import (
        build_article_package as build_v2,
    )
    from qveris_bench.articles.factory_v2 import (
        reproduce_article_package as reproduce_v2,
    )

    output = tmp_path / "publication"
    profile = _profile(tmp_path / "profile.yaml")
    built = build_v2(SNAPSHOT, profile, output)
    manifest = json.loads(built.manifest.read_text(encoding="utf-8"))
    manifest["charts"].pop("market-coverage.png")
    built.manifest.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ArticleBuildError, match="chart set differs"):
        reproduce_v2(SNAPSHOT, profile, output)
