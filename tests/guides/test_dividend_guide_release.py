from __future__ import annotations

import hashlib
import json
import platform
import re
from datetime import datetime
from pathlib import Path

import pytest
import yaml
from PIL import Image

from qveris_bench.profiles.selection import build_selection_snapshot
from scripts.render_cap_guide_charts import (
    render_dividend_evidence_heatmap,
    render_release_outcomes,
    render_selection_tradeoff,
)

ROOT = Path(__file__).resolve().parents[2]
ARTICLE = ROOT / "docs/guides/best-dividend-apis.md"
MANIFEST = ROOT / "docs/guides/capability-seo/best-dividend-apis/manifest.yaml"
RELEASE_DIR = ROOT / "releases/dividend-events-2026-q3-v1"
CASES = ROOT / "cap_packs/dividend_events/cases.yaml"
PIPELINE_DOC = ROOT / "docs/how-a-cap-becomes-an-article.html"
RELEASE_DIGEST = (
    "sha256:ff44f0d4aa72553949d93910c78af57c29bf46dc39a206aacb97956a081049e0"
)
EVIDENCE_CHARTS = (
    "capability-seo/best-dividend-apis/charts/dividend-evidence-heatmap.png",
    "capability-seo/best-dividend-apis/charts/dividend-runtime-tradeoff.png",
    "capability-seo/best-dividend-apis/charts/dividend-market-coverage.png",
)
MANIFEST_EVIDENCE_CHARTS = tuple(f"docs/guides/{target}" for target in EVIDENCE_CHARTS)


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


def test_article_evidence_charts_are_declared_and_valid_image() -> None:
    article = ARTICLE.read_text(encoding="utf-8")
    manifest = yaml.safe_load(MANIFEST.read_text(encoding="utf-8"))

    assert manifest["artifacts"]["charts"] == list(MANIFEST_EVIDENCE_CHARTS)
    assert manifest["artifacts"]["charts_manifest"].endswith(
        "evidence-matrix-manifest.json"
    )
    for target in EVIDENCE_CHARTS:
        assert target in article
        path = ARTICLE.parent / target
        assert path.is_file()
        with Image.open(path) as chart:
            assert chart.width >= 1600
            assert chart.height >= 900
            assert chart.width > chart.height
    assert "完整事件日期组" not in article
    assert "date-timeline.svg" not in article
    assert "dividend-api-evidence-matrix.svg" not in article


def test_evidence_charts_encode_access_path_identity_and_scenarios() -> None:
    chart_manifest = json.loads(
        (MANIFEST.parent / "charts/evidence-matrix-manifest.json").read_text(
            encoding="utf-8"
        )
    )
    matrix = json.dumps(chart_manifest["data"], ensure_ascii=False)
    rows = chart_manifest["data"]["rows"]
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
    assert sum(row["meta"].startswith("QVeris") for row in rows) == 5
    assert "不代表全市场能力" in matrix
    assert matrix.count("A 股 · 600519.SH") == 2
    assert matrix.count("美股 · AAPL") == 4


def test_committed_evidence_charts_are_release_derived(tmp_path: Path) -> None:
    chart_dir = MANIFEST.parent / "charts"
    generated = render_dividend_evidence_heatmap(
        RELEASE_DIR,
        ROOT / "evidence/dividend-events-2026-q3-v1",
        tmp_path,
        edition_date="2026-08-11",
    )

    committed = json.loads(
        (chart_dir / "evidence-matrix-manifest.json").read_text(encoding="utf-8")
    )
    assert generated["data"] == committed["data"]
    assert generated["input_digests"] == committed["input_digests"]
    assert generated["rendered_at"] == committed["rendered_at"]
    assert generated["charts"] == committed["charts"]
    manifest = yaml.safe_load(MANIFEST.read_text(encoding="utf-8"))
    assert manifest["artifacts"]["selection_charts_manifest_digest"] == (
        f"sha256:{hashlib.sha256((committed_dir / 'selection-charts-manifest.json').read_bytes()).hexdigest()}"
    )
    assert generated["input_digests"]["release"] == RELEASE_DIGEST
    chart_name = "dividend-evidence-heatmap.png"
    if platform.system() == "Linux":
        assert (tmp_path / chart_name).read_bytes() == (
            chart_dir / chart_name
        ).read_bytes()
    assert committed["charts"][chart_name] == (
        f"sha256:{hashlib.sha256((chart_dir / chart_name).read_bytes()).hexdigest()}"
    )


def test_evidence_chart_footer_uses_requested_edition_date(tmp_path: Path) -> None:
    manifest = render_dividend_evidence_heatmap(
        RELEASE_DIR,
        ROOT / "evidence/dividend-events-2026-q3-v1",
        tmp_path,
        edition_date="2026-11-01",
    )

    assert "2026-11-01" in manifest["data"]["footer"]


def test_selection_tradeoff_chart_is_snapshot_derived(tmp_path: Path) -> None:
    snapshot = MANIFEST.parent / "selection-snapshot.json"
    generated = render_selection_tradeoff(snapshot, tmp_path)
    committed_dir = MANIFEST.parent / "charts"
    committed = json.loads(
        (committed_dir / "selection-charts-manifest.json").read_text(encoding="utf-8")
    )

    assert generated["data"] == committed["data"]
    assert generated["input_digests"] == committed["input_digests"]
    assert generated["rendered_at"] == committed["rendered_at"]
    assert generated["input_digests"]["selection_snapshot"] == (
        f"sha256:{hashlib.sha256(snapshot.read_bytes()).hexdigest()}"
    )
    for chart_name, digest in committed["charts"].items():
        if platform.system() == "Linux":
            assert (tmp_path / chart_name).read_bytes() == (
                committed_dir / chart_name
            ).read_bytes()
        assert digest == (
            "sha256:"
            + hashlib.sha256((committed_dir / chart_name).read_bytes()).hexdigest()
        )
    assert len(generated["data"]["rows"]) == 5
    assert all(row["access_path"] == "QVeris" for row in generated["data"]["rows"])


def test_selection_market_coverage_chart_reuses_verified_snapshot_states(
    tmp_path: Path,
) -> None:
    snapshot = MANIFEST.parent / "selection-snapshot.json"
    generated = render_selection_tradeoff(snapshot, tmp_path)
    market_chart = tmp_path / "dividend-market-coverage.png"

    assert market_chart.is_file(), "AC1 must render the Finlight-style market matrix"
    market_data = generated["data"]["market_coverage"]
    assert market_data["title"] == (
        "QVeris SV 市场正向证据：EODHD 24 个市场，恒生聚源 CN"
    )
    assert market_data["highlighted_access_paths"] == [
        ["eodhd", "eodhd-dividends-qveris"]
    ]
    assert market_data["edition"] == "2026-08-12"
    assert market_data["observation_window"] == {
        "start": "2026-07-20",
        "end": "2026-08-12",
    }
    assert market_data["markets"] == [
        "AT",
        "BE",
        "BR",
        "CH",
        "CL",
        "CN",
        "CO",
        "CZ",
        "DE",
        "DK",
        "ES",
        "FI",
        "FR",
        "GR",
        "HK",
        "ID",
        "IE",
        "NL",
        "NO",
        "PH",
        "PT",
        "SE",
        "TH",
        "TW",
        "US",
    ]
    rows = {row["provider_id"]: row for row in market_data["rows"]}
    assert rows["eodhd"]["verified_markets"] == [
        market for market in market_data["markets"] if market != "CN"
    ]
    assert rows["hangseng"]["verified_markets"] == ["CN"]
    assert rows["ifind"]["state"] == "not_applicable"
    assert all(
        rows[provider_id]["state"] == "evidence_insufficient"
        for provider_id in ("alpha-vantage", "massive-stocks", "twelve-data")
    )
    assert generated["charts"][market_chart.name] == (
        f"sha256:{hashlib.sha256(market_chart.read_bytes()).hexdigest()}"
    )
    if platform.system() == "Linux":
        assert (
            market_chart.read_bytes()
            == (MANIFEST.parent / "charts" / market_chart.name).read_bytes()
        )


def test_selection_market_chart_preserves_every_access_path_identity(
    tmp_path: Path,
) -> None:
    snapshot = json.loads((MANIFEST.parent / "selection-snapshot.json").read_text())
    extra = json.loads(json.dumps(snapshot["rows"][0]))
    extra.update(
        {
            "provider_id": "alpha-vantage-alt",
            "provider_name": "Alpha Vantage Alt",
            "access_path_id": "alpha-vantage-dividends-alt-qveris",
        }
    )
    snapshot["rows"].append(extra)
    path = tmp_path / "selection.json"
    path.write_text(json.dumps(snapshot), encoding="utf-8")

    rendered = render_selection_tradeoff(path, tmp_path / "charts")
    identities = {
        (row["provider_id"], row["access_path_id"])
        for row in rendered["data"]["market_coverage"]["rows"]
    }
    assert identities == {
        (row["provider_id"], row["access_path_id"]) for row in snapshot["rows"]
    }


def test_selection_market_chart_changes_with_edition(tmp_path: Path) -> None:
    snapshot = json.loads((MANIFEST.parent / "selection-snapshot.json").read_text())
    first_path = tmp_path / "first.json"
    first_path.write_text(json.dumps(snapshot), encoding="utf-8")
    first = render_selection_tradeoff(first_path, tmp_path / "first")

    snapshot["edition"] = "2026-08-13"
    second_path = tmp_path / "second.json"
    second_path.write_text(json.dumps(snapshot), encoding="utf-8")
    second = render_selection_tradeoff(second_path, tmp_path / "second")

    chart_name = "dividend-market-coverage.png"
    assert first["charts"][chart_name] != second["charts"][chart_name]
    assert first["data"]["market_coverage"]["edition"] == "2026-08-12"
    assert second["data"]["market_coverage"]["edition"] == "2026-08-13"


def test_article_embeds_market_coverage_chart_next_to_market_section() -> None:
    article = ARTICLE.read_text(encoding="utf-8")
    market_section = article.split("### 市场覆盖：", 1)[1].split("## 6 家供应商", 1)[0]
    chart_path = "capability-seo/best-dividend-apis/charts/dividend-market-coverage.png"

    assert f"]({chart_path})]({chart_path})" in market_section
    assert "绿色只表示 SV 正向证据" in market_section


def test_selection_tradeoff_chart_rejects_inconsistent_sample_sizes(
    tmp_path: Path,
) -> None:
    snapshot = json.loads((MANIFEST.parent / "selection-snapshot.json").read_text())
    snapshot["rows"][0]["gateway_metrics"]["latency_sample_size"] = 5
    path = tmp_path / "selection.json"
    path.write_text(json.dumps(snapshot), encoding="utf-8")

    with pytest.raises(ValueError, match="consistent sample sizes"):
        render_selection_tradeoff(path, tmp_path / "charts")


def test_manifest_uses_public_release_as_source_of_truth() -> None:
    manifest = yaml.safe_load(MANIFEST.read_text(encoding="utf-8"))

    assert manifest["benchmark_id"] == "dividend-events-2026-q3-v1"
    assert manifest["release"]["digest"] == RELEASE_DIGEST
    assert manifest["release"]["applicable_cells"] == 36
    assert all(case["minimum_rounds"] == 3 for case in manifest["scenarios"])
    assert manifest["native_supplements"] == ["同花顺 iFinD"]
    assert "同花顺 iFinD" not in manifest["seo"]["provider_pages"]
    assert "direct_test_evidence" not in manifest["artifacts"]
    snapshot = ROOT / manifest["artifacts"]["selection_snapshot"]
    assert snapshot.is_file()
    assert manifest["selection_snapshot"]["digest"] == (
        f"sha256:{hashlib.sha256(snapshot.read_bytes()).hexdigest()}"
    )
    snapshot_input = ROOT / manifest["artifacts"]["selection_snapshot_input"]
    fresh = build_selection_snapshot(snapshot_input, ROOT)
    assert fresh.json_bytes == snapshot.read_bytes()
    assert manifest["selection_snapshot"]["input_digest"] == (
        f"sha256:{hashlib.sha256(snapshot_input.read_bytes()).hexdigest()}"
    )
    sv_snapshot = ROOT / manifest["artifacts"]["qveris_sv_snapshot"]
    assert manifest["qveris_sv"]["digest"] == (
        f"sha256:{hashlib.sha256(sv_snapshot.read_bytes()).hexdigest()}"
    )
    sv_document = json.loads(sv_snapshot.read_text(encoding="utf-8"))
    assert sv_document["disclosure_level"] == "sanitized_public"
    assert sv_document["license_status"] == "cleared"
    assert len(sv_document["results"]) == 25
    assert all(result["supported"] is True for result in sv_document["results"])
    assert "tool_id" not in sv_snapshot.read_text(encoding="utf-8")
    assert manifest["qveris_sv"]["id"] == sv_document["snapshot_id"]
    assert (
        manifest["qveris_sv"]["observation_window"] == sv_document["observation_window"]
    )
    assert manifest["qveris_sv"]["verified_results"] == len(sv_document["results"])
    assert (
        manifest["qveris_sv"]["source_rows_digest"] == sv_document["source_rows_digest"]
    )
    assert manifest["qveris_sv"]["bindings_digest"] == sv_document["bindings_digest"]
    bindings = ROOT / manifest["artifacts"]["qveris_sv_bindings"]
    bindings_digest = f"sha256:{hashlib.sha256(bindings.read_bytes()).hexdigest()}"
    assert manifest["qveris_sv"]["bindings_digest"] == bindings_digest
    assert sv_document["bindings_digest"] == bindings_digest
    identity_map = ROOT / manifest["artifacts"]["qveris_sv_identity_map"]
    identity_map_digest = (
        f"sha256:{hashlib.sha256(identity_map.read_bytes()).hexdigest()}"
    )
    assert manifest["qveris_sv"]["identity_map_digest"] == identity_map_digest
    assert sv_document["identity_map_digest"] == identity_map_digest


def test_article_answers_runtime_price_coverage_and_agent_decisions() -> None:
    article = ARTICLE.read_text(encoding="utf-8")

    for phrase in (
        "QVeris gateway 延迟中位数",
        "成功调用 credits 中位数",
        "官方价格",
        "市场覆盖",
        "MKT.DIVIDENDS",
        "参数清晰度",
        "schema 稳定性",
        "错误恢复",
    ):
        assert phrase in article
    assert "491 ms / 0.237 credits" in article
    assert "576 ms / 0.200 credits" in article
    assert "779 ms / 0.281 credits" in article
    assert "861 ms / 0.100 credits" in article
    assert "综合 AI 友好度" not in article
    assert "已验证全球市场覆盖" not in article


def test_article_publishes_measured_sv_coverage_near_the_decision_table() -> None:
    article = ARTICLE.read_text(encoding="utf-8")
    snapshot = json.loads((MANIFEST.parent / "selection-snapshot.json").read_text())
    overview_rows = _markdown_table_rows(article, "| 供应商与 Access Path |")
    market_rows = _markdown_table_rows(article, "本次固定市场样本")

    assert "QVeris SV 市场证据" in article.split("## 为什么分红 API", 1)[0]
    assert "24 个已验证市场" in _provider_row(overview_rows, "EODHD", "QVeris")[4]
    assert "CN 已验证" in _provider_row(overview_rows, "恒生聚源", "QVeris")[4]
    eodhd = next(row for row in snapshot["rows"] if row["provider_id"] == "eodhd")
    assert eodhd["market_coverage"]["sv_state"] == "measured"
    assert len(eodhd["market_coverage"]["sv_verified_markets"]) == 24
    eodhd_market_row = _provider_row(market_rows, "EODHD", "QVeris")
    published_markets = {
        item.strip() for item in eodhd_market_row[2].split(",") if item.strip()
    }
    assert published_markets == set(eodhd["market_coverage"]["sv_verified_markets"])
    hangseng_market_row = _provider_row(market_rows, "恒生聚源", "QVeris")
    assert hangseng_market_row[2] == "CN"
    sv_document = json.loads((MANIFEST.parent / "qveris-sv-snapshot.json").read_text())
    window = sv_document["observation_window"]
    capture_date = datetime.fromisoformat(
        sv_document["source_snapshot_captured_at"].replace("Z", "+00:00")
    ).date()
    assert f"{window['start']} 至 {window['end']}" in article
    assert f"抓取于 {capture_date.isoformat()}" in article
    assert "SV 验证的是这条 Tool × Capability 的市场可达性" in article


def test_article_selection_facts_match_every_snapshot_row() -> None:
    article = ARTICLE.read_text(encoding="utf-8")
    snapshot = json.loads((MANIFEST.parent / "selection-snapshot.json").read_text())
    aliases = {"Massive Stocks": "Massive"}
    runtime_rows = _markdown_table_rows(article, "| 供应商与 Access Path |")
    pricing_rows = _markdown_table_rows(article, "| Provider / Access Path |")
    market_rows = _markdown_table_rows(article, "本次固定市场样本")

    for row in snapshot["rows"]:
        provider = aliases.get(row["provider_name"], row["provider_name"])
        access_path = (
            "Native MCP" if row["access_path_type"] == "native_mcp" else "QVeris"
        )
        runtime_row = _provider_row(runtime_rows, provider, access_path)
        metrics = row["gateway_metrics"]
        if metrics["state"] == "measured":
            runtime = (
                f"{metrics['latency_median_ms']:.0f} ms / "
                f"{metrics['median_credits']:.3f} credits"
            )
            assert runtime in runtime_row[2]
        else:
            assert "不适用" in runtime_row[2]

        pricing_row = _provider_row(pricing_rows, provider, access_path)
        pricing = row["official_pricing"]
        if pricing["state"] == "declared":
            assert pricing["pricing_url"] in pricing_row[0]
            assert pricing["free_tier"] in pricing_row[1]
            assert pricing["paid_plans"] in pricing_row[2]
        else:
            assert "Evidence insufficient" in pricing_row[1]
            assert "Evidence insufficient" in pricing_row[2]

        market_row = _provider_row(market_rows, provider, access_path)
        coverage = row["market_coverage"]
        for market in coverage["tested_markets"]:
            assert f"{market} ·" in market_row[1]
        sv_label = {
            "evidence_insufficient": "**Evidence insufficient**",
            "not_applicable": "不适用",
            "measured": ", ".join(coverage["sv_verified_markets"]),
        }[coverage["sv_state"]]
        assert market_row[2] == sv_label


def _markdown_table_rows(article: str, header_fragment: str) -> list[list[str]]:
    lines = article.splitlines()
    header_index = next(
        index for index, line in enumerate(lines) if header_fragment in line
    )
    rows: list[list[str]] = []
    for line in lines[header_index + 2 :]:
        if not line.startswith("|"):
            break
        rows.append([cell.strip() for cell in line.strip("|").split("|")])
    return rows


def _provider_row(rows: list[list[str]], provider: str, access_path: str) -> list[str]:
    matches = [row for row in rows if provider in row[0] and access_path in row[0]]
    assert len(matches) == 1
    return matches[0]


def test_article_embeds_only_decision_useful_snapshot_chart() -> None:
    article = ARTICLE.read_text(encoding="utf-8")

    assert "dividend-runtime-tradeoff.png" in article
    assert "chart-market-coverage.png" not in article
    assert "chart-ai-difficulty.png" not in article


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
