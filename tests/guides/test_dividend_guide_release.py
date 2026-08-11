from __future__ import annotations

import hashlib
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest
import yaml

from scripts.render_cap_guide_charts import render_release_outcomes

ROOT = Path(__file__).resolve().parents[2]
ARTICLE = ROOT / "docs/guides/best-dividend-apis.md"
MANIFEST = ROOT / "docs/guides/capability-seo/best-dividend-apis/manifest.yaml"
RELEASE_DIR = ROOT / "releases/dividend-events-2026-q3-v1"
CASES = ROOT / "cap_packs/dividend_events/cases.yaml"
PIPELINE_DOC = ROOT / "docs/how-a-cap-becomes-an-article.html"
RELEASE_DIGEST = (
    "sha256:ff44f0d4aa72553949d93910c78af57c29bf46dc39a206aacb97956a081049e0"
)
EDITORIAL_VISUALS = (
    "capability-seo/best-dividend-apis/charts/dividend-event-date-timeline.svg",
    "capability-seo/best-dividend-apis/charts/dividend-api-evidence-matrix.svg",
)
MANIFEST_EDITORIAL_VISUALS = tuple(
    f"docs/guides/{target}" for target in EDITORIAL_VISUALS
)


def test_article_is_bound_to_dividend_release() -> None:
    article = ARTICLE.read_text(encoding="utf-8")

    assert "dividend-events-2026-q3-v1" in article
    assert RELEASE_DIGEST in article
    assert "3 轮" in article
    assert "36 次" in article
    assert "同花顺 iFinD（Native MCP）" in article
    assert "Not qualified" in article
    assert "https://qveris.ai/providers/ths_ifind" not in article
    assert "AI 友好度" not in article
    assert "Direct Test 4/4" not in article


def test_article_has_only_verified_qveris_provider_calls_to_action() -> None:
    article = ARTICLE.read_text(encoding="utf-8")
    provider_pages = {
        "hangseng": "https://qveris.ai/providers/hangseng_polysource",
        "twelve-data": "https://qveris.ai/providers/twelvedata",
        "alpha-vantage": "https://qveris.ai/providers/alphavantage",
        "eodhd": "https://qveris.ai/providers/eodhd",
        "massive": "https://qveris.ai/providers/massive_stocks",
    }

    for page in provider_pages.values():
        assert page in article
    assert article.count("Try it in QVeris") == len(provider_pages)


def test_article_exposes_agent_signals_without_an_aggregate_rating() -> None:
    article = ARTICLE.read_text(encoding="utf-8")

    assert "## Direct Test 可观察的 Agent 接入风险信号" in article
    for signal in (
        "必需事件字段",
        "证券身份",
        "无效 symbol",
        "响应内币种",
        "附加事件日期",
        "参数清晰度、分页和 Agent Trial",
    ):
        assert signal in article
    assert "AI 友好度" not in article
    assert "Agent 总分" not in article
    assert "与 `AAPL` 对应" not in article
    assert article.count("身份一致性未独立测量") == 5


def test_article_editorial_visuals_are_declared_and_valid_svg() -> None:
    article = ARTICLE.read_text(encoding="utf-8")
    manifest = yaml.safe_load(MANIFEST.read_text(encoding="utf-8"))

    assert manifest["artifacts"]["editorial_visuals"] == list(
        MANIFEST_EDITORIAL_VISUALS
    )
    for target in EDITORIAL_VISUALS:
        assert target in article
        path = ARTICLE.parent / target
        assert path.is_file()
        root = ET.parse(path).getroot()
        assert root.tag == "{http://www.w3.org/2000/svg}svg"
        width, height = (int(value) for value in root.attrib["viewBox"].split()[2:])
        assert width <= 760
        assert height > width
    assert "完整事件日期组" not in article
    assert "decision-tree.svg" not in article
    assert "evidence-chain.svg" not in article
    assert all("market-coverage" not in target for target in EDITORIAL_VISUALS)


def test_editorial_visuals_encode_date_semantics_and_access_path_identity() -> None:
    timeline = "".join(
        ET.parse(ARTICLE.parent / EDITORIAL_VISUALS[0]).getroot().itertext()
    )
    matrix = "".join(
        ET.parse(ARTICLE.parent / EDITORIAL_VISUALS[1]).getroot().itertext()
    )

    for date_name in (
        "Declaration Date",
        "Ex-Dividend Date",
        "Record Date",
        "Payment Date",
    ):
        assert date_name in timeline
    for provider in (
        "恒生聚源",
        "同花顺 iFinD",
        "Twelve Data",
        "Alpha Vantage",
        "EODHD",
        "Massive",
    ):
        assert provider in matrix
    assert "Native MCP" in matrix
    assert matrix.count("QVeris") == 10
    assert "不代表全市场能力" in matrix


def test_manifest_uses_public_release_as_source_of_truth() -> None:
    manifest = yaml.safe_load(MANIFEST.read_text(encoding="utf-8"))

    assert manifest["benchmark_id"] == "dividend-events-2026-q3-v1"
    assert manifest["release"]["digest"] == RELEASE_DIGEST
    assert manifest["release"]["applicable_cells"] == 36
    assert all(case["minimum_rounds"] == 3 for case in manifest["scenarios"])
    assert manifest["native_supplements"] == ["同花顺 iFinD"]
    assert "同花顺 iFinD" not in manifest["seo"]["provider_pages"]
    assert "direct_test_evidence" not in manifest["artifacts"]


def test_release_chart_is_derived_from_release_bytes(tmp_path: Path) -> None:
    chart_manifest = render_release_outcomes(
        RELEASE_DIR,
        CASES,
        tmp_path,
        edition_date="2026-08-11",
    )

    assert (tmp_path / "chart-direct-outcomes.png").is_file()
    assert chart_manifest["input_digests"]["release"] == (
        "sha256:"
        + hashlib.sha256((RELEASE_DIR / "release.json").read_bytes()).hexdigest()
    )
    assert chart_manifest["input_digests"]["cases"] == (
        f"sha256:{hashlib.sha256(CASES.read_bytes()).hexdigest()}"
    )
    assert chart_manifest["release_id"] == "dividend-events-2026-q3-v1"
    written = json.loads(
        (tmp_path / "charts-manifest.json").read_text(encoding="utf-8")
    )
    assert written == chart_manifest


def test_release_chart_rejects_unclassified_cases(tmp_path: Path) -> None:
    document = json.loads((RELEASE_DIR / "release.json").read_text(encoding="utf-8"))
    applicable = next(cell for cell in document["cells"] if cell["applicable"])
    applicable["case_id"] = "unclassified-case"
    release_dir = tmp_path / "release"
    release_dir.mkdir()
    (release_dir / "release.json").write_text(
        json.dumps(document),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="absent from CAP Pack"):
        render_release_outcomes(
            release_dir,
            CASES,
            tmp_path / "charts",
            edition_date="2026-08-11",
        )


def test_committed_chart_manifest_binds_release_and_chart() -> None:
    chart_dir = MANIFEST.parent / "charts"
    chart_path = chart_dir / "chart-direct-outcomes.png"
    chart_manifest = json.loads(
        (chart_dir / "charts-manifest.json").read_text(encoding="utf-8")
    )

    assert chart_manifest["input_digests"]["release"] == RELEASE_DIGEST
    assert chart_manifest["input_digests"]["cases"] == (
        f"sha256:{hashlib.sha256(CASES.read_bytes()).hexdigest()}"
    )
    assert chart_manifest["charts"][chart_path.name] == (
        f"sha256:{hashlib.sha256(chart_path.read_bytes()).hexdigest()}"
    )


def test_article_relative_links_resolve_in_repository() -> None:
    article = ARTICLE.read_text(encoding="utf-8")
    relative_targets = [
        target
        for target in re.findall(r"\]\(([^)]+)\)", article)
        if not target.startswith(("https://", "http://", "mailto:"))
    ]

    assert relative_targets
    for target in relative_targets:
        path = target.split("#", 1)[0]
        assert (ARTICLE.parent / path).resolve().exists(), target


def test_legacy_dividend_probe_artifacts_are_not_publication_inputs() -> None:
    publication_dir = MANIFEST.parent

    assert not (publication_dir / "probe-evidence-2026-08-10.json").exists()
    assert not (publication_dir / "charts/chart-latency-cost.png").exists()
    assert not (publication_dir / "charts/chart-market-coverage.png").exists()


def test_pipeline_doc_describes_the_release_first_path() -> None:
    document = PIPELINE_DOC.read_text(encoding="utf-8")

    assert "immutable release" in document
    assert "至少 3 轮" in document
    assert "dividend-events-2026-q3-v1" in document
    assert "固定用例 × 2 轮" not in document
    assert "AI 友好度" not in document
    assert "6 家全部 4/4" not in document
