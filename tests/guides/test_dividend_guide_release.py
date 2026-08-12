from __future__ import annotations

import hashlib
import json
import re
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
    assert "本次样本未通过" in article
    assert "https://qveris.ai/providers/ths_ifind" not in article
    assert "AI 友好度" not in article
    assert "Direct Test 4/4" not in article


def test_article_uses_reader_facing_outcomes_and_one_decision_flow() -> None:
    article = ARTICLE.read_text(encoding="utf-8")

    for internal_term in ("Qualified", "Not qualified", "Evidence insufficient"):
        assert internal_term not in article
    for public_state in (
        "本次样本通过",
        "本次样本未通过",
        "证据不足",
        "未测试：明确不适用",
    ):
        assert public_state in article

    headings = [
        "## 实测结论一览",
        "## 开发者怎么选",
        "## 证据与供应商差异",
        "## Agent 选型时额外检查什么",
        "## 测试方法、复测与贡献",
        "## 限制、披露与更正",
        "## 常见问题",
    ]
    positions = [article.index(heading) for heading in headings]
    assert positions == sorted(positions)
    assert "## AI Agent 接入时要做的 5 件事" not in article


def test_article_publishes_inspect_list_prices_not_discounted_account_costs() -> None:
    article = ARTICLE.read_text(encoding="utf-8")
    overview_rows = _markdown_table_rows(article, "| 供应商与 Access Path |")
    expected = {
        "恒生聚源": "1 credit/call",
        "Twelve Data": "2.37 credits/call",
        "Alpha Vantage": "2 credits/call",
        "EODHD": "2.81 credits/call",
        "Massive": "1 credit/call",
    }

    for provider, list_price in expected.items():
        row = _provider_row(overview_rows, provider, "QVeris")
        assert list_price in row[2]
    for discounted in (
        "0.100 credits",
        "0.200 credits",
        "0.237 credits",
        "0.281 credits",
    ):
        assert discounted not in article
    assert "QVeris Inspect 公开标价" in article
    assert "账号实际扣费" in article
    assert "https://massive.com/pricing?product=stocks" in article
    assert "Stocks Basic Free" in article


def test_article_explains_market_samples_and_evidence_heatmap() -> None:
    article = ARTICLE.read_text(encoding="utf-8")

    for phrase in (
        "代表市场样本结果",
        "通过（2/2）",
        "本次代表样本未通过（0/2）",
        "未测试：明确不适用",
        "不能据此断言供应商完全不支持该市场",
        "核心可用性",
        "响应字段丰富度",
        "未独立测量不等于失败",
        "字段丰富不等于记录可用",
    ):
        assert phrase in article


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

    assert "## Agent 选型时额外检查什么" in article
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
    assert generated["input_digests"]["release"] == RELEASE_DIGEST
    chart_name = "dividend-evidence-heatmap.png"
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
    manifest = yaml.safe_load(MANIFEST.read_text(encoding="utf-8"))
    assert manifest["artifacts"]["selection_charts_manifest_digest"] == (
        "sha256:"
        + hashlib.sha256(
            (committed_dir / "selection-charts-manifest.json").read_bytes()
        ).hexdigest()
    )
    assert generated["input_digests"]["selection_snapshot"] == (
        f"sha256:{hashlib.sha256(snapshot.read_bytes()).hexdigest()}"
    )
    for chart_name, digest in committed["charts"].items():
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
        "9 个代表市场 × 6 条 Access Path：Dividend Event 实测结果"
    )
    assert market_data["edition"] == "2026-08-12"
    assert market_data["observation_date"] == "2026-08-12"
    assert market_data["release_digest"].startswith("sha256:")
    assert market_data["markets"] == [
        "US",
        "HK",
        "CN",
        "JP",
        "DE",
        "FR",
        "BR",
        "IN",
        "ES",
    ]
    rows = {row["provider_id"]: row for row in market_data["rows"]}
    assert rows["eodhd"]["results"]["US"]["state"] == "verified"
    assert rows["eodhd"]["results"]["JP"]["state"] == "provider_negative"
    assert rows["hangseng"]["results"]["CN"]["state"] == "verified"
    assert rows["hangseng"]["results"]["US"]["state"] == "not_applicable"
    assert rows["ifind"]["results"]["US"]["state"] == "provider_negative"
    assert generated["charts"][market_chart.name] == (
        f"sha256:{hashlib.sha256(market_chart.read_bytes()).hexdigest()}"
    )


def test_selection_market_chart_preserves_every_access_path_identity(
    tmp_path: Path,
) -> None:
    snapshot = json.loads((MANIFEST.parent / "selection-snapshot.json").read_text())
    extra = json.loads(json.dumps(snapshot["rows"][0]))
    extra.update(
        {
            "provider_id": "alpha-vantage",
            "provider_name": "Alpha Vantage",
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
    labels = [row["label"] for row in rendered["data"]["market_coverage"]["rows"]]
    assert len(labels) == len(set(labels))
    assert "× 7 条 Access Path" in rendered["data"]["market_coverage"]["title"]


def test_selection_market_chart_derives_round_labels(tmp_path: Path) -> None:
    snapshot = json.loads((MANIFEST.parent / "selection-snapshot.json").read_text())
    for row in snapshot["rows"]:
        for result in row["market_coverage"]["results"]:
            result["total_rounds"] = 3
            if result["state"] == "verified":
                result["passed_rounds"] = 3
    path = tmp_path / "selection.json"
    path.write_text(json.dumps(snapshot), encoding="utf-8")

    rendered = render_selection_tradeoff(path, tmp_path / "charts")
    result = rendered["data"]["market_coverage"]["rows"][0]["results"]["CN"]
    assert result["passed_rounds"] == result["total_rounds"] == 3


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
    market_section = article.split("### 九个代表市场的样本结果", 1)[1].split(
        "### 六家供应商逐一分析", 1
    )[0]
    chart_path = "capability-seo/best-dividend-apis/charts/dividend-market-coverage.png"

    assert f"]({chart_path})]({chart_path})" in market_section
    assert "图中绿色表示该市场的固定代表 symbol 连续两轮" in market_section


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
    pricing = ROOT / manifest["artifacts"]["qveris_list_pricing"]
    assert manifest["qveris_list_pricing"]["digest"] == (
        f"sha256:{hashlib.sha256(pricing.read_bytes()).hexdigest()}"
    )
    assert manifest["qveris_list_pricing"]["source"] == "qveris_inspect"
    assert manifest["qveris_list_pricing"]["inspected_at"] == "2026-08-12"
    market_release = ROOT / manifest["artifacts"]["market_coverage_release"]
    assert manifest["market_coverage_release"]["digest"] == (
        f"sha256:{hashlib.sha256(market_release.read_bytes()).hexdigest()}"
    )
    assert manifest["market_coverage_release"]["planned_cells"] == 120
    assert manifest["market_coverage_release"]["applicable_cells"] == 66
    market_evidence = ROOT / manifest["artifacts"]["market_coverage_public_evidence"]
    assert len(tuple(market_evidence.glob("*.json"))) == 66


def test_article_answers_runtime_price_coverage_and_agent_decisions() -> None:
    article = ARTICLE.read_text(encoding="utf-8")

    for phrase in (
        "QVeris gateway 延迟中位数",
        "QVeris Inspect 公开标价",
        "官方价格",
        "代表市场样本",
        "9 个代表市场",
        "参数清晰度",
        "schema 稳定性",
        "错误恢复",
    ):
        assert phrase in article
    assert "491 ms / 2.37 credits/call" in article
    assert "576 ms / 2 credits/call" in article
    assert "779 ms / 2.81 credits/call" in article
    assert "861 ms / 1 credit/call" in article
    assert "综合 AI 友好度" not in article
    assert "已验证全球市场覆盖" not in article


def test_article_publishes_released_market_coverage_near_the_decision_table() -> None:
    article = ARTICLE.read_text(encoding="utf-8")
    snapshot = json.loads((MANIFEST.parent / "selection-snapshot.json").read_text())
    overview_rows = _markdown_table_rows(article, "| 供应商与 Access Path |")
    market_rows = _markdown_table_rows(article, "通过（2/2）的代表市场")

    assert "7 个市场通过（2/2）" in _provider_row(
        overview_rows, "EODHD", "QVeris"
    )[4]
    assert "CN 通过（2/2）" in _provider_row(
        overview_rows, "恒生聚源", "QVeris"
    )[4]
    eodhd = next(row for row in snapshot["rows"] if row["provider_id"] == "eodhd")
    verified = {
        result["market"]
        for result in eodhd["market_coverage"]["results"]
        if result["state"] == "verified"
    }
    assert verified == {"US", "HK", "CN", "DE", "FR", "BR", "ES"}
    eodhd_market_row = _provider_row(market_rows, "EODHD", "QVeris")
    published_markets = {
        item.strip() for item in eodhd_market_row[1].split(",") if item.strip()
    }
    assert published_markets == verified
    hangseng_market_row = _provider_row(market_rows, "恒生聚源", "QVeris")
    assert hangseng_market_row[1] == "CN"
    assert "66 次真实调用" in article
    assert "54 个明确不适用单元" in article


def test_article_summary_is_exactly_bound_to_base_and_market_releases() -> None:
    article = ARTICLE.read_text(encoding="utf-8")
    snapshot = json.loads((MANIFEST.parent / "selection-snapshot.json").read_text())
    overview_rows = _markdown_table_rows(article, "| 供应商与 Access Path |")
    expected_base = {
        "恒生聚源": "**证据不足**",
        "同花顺 iFinD": "**本次样本未通过**",
        "Twelve Data": "**本次样本通过**",
        "Alpha Vantage": "**本次样本通过**",
        "EODHD": "**本次样本通过**",
        "Massive": "**本次样本通过**",
    }
    aliases = {"Massive Stocks": "Massive"}
    for row in snapshot["rows"]:
        provider = aliases.get(row["provider_name"], row["provider_name"])
        access_path = (
            "Native MCP" if row["access_path_type"] == "native_mcp" else "QVeris"
        )
        overview = _provider_row(overview_rows, provider, access_path)
        assert expected_base[provider] in overview[1]
        verified = sum(
            result["state"] == "verified"
            for result in row["market_coverage"]["results"]
        )
        applicable = sum(
            result["state"] != "not_applicable"
            for result in row["market_coverage"]["results"]
        )
        if provider == "Alpha Vantage":
            assert f"{verified} 个适用市场通过（2/2）" in overview[4]
        elif provider in {"EODHD", "Twelve Data"}:
            assert f"{verified} 个市场通过（2/2）" in overview[4]
        elif provider == "恒生聚源":
            assert "CN 通过（2/2）" in overview[4]
        assert (
            applicable
            + sum(
                result["state"] == "not_applicable"
                for result in row["market_coverage"]["results"]
            )
            == 9
        )
    assert "市场补充套件改为优先读取响应 `stockcode`" in article
    assert "需要生成新的三轮 successor release" in article

    quick_advice = article.split("> **快速建议**：", 1)[1].split("\n", 1)[0]
    by_provider = {row["provider_id"]: row for row in snapshot["rows"]}
    eodhd_verified = sum(
        result["state"] == "verified"
        for result in by_provider["eodhd"]["market_coverage"]["results"]
    )
    twelve_verified = sum(
        result["state"] == "verified"
        for result in by_provider["twelve-data"]["market_coverage"]["results"]
    )
    alpha_results = by_provider["alpha-vantage"]["market_coverage"]["results"]
    alpha_verified = sum(result["state"] == "verified" for result in alpha_results)
    alpha_not_applicable = sum(
        result["state"] == "not_applicable" for result in alpha_results
    )
    assert f"EODHD 的代表样本通过 {eodhd_verified} 个市场" in quick_advice
    assert f"Twelve Data 通过 {twelve_verified} 个" in quick_advice
    assert f"Alpha Vantage 的 {alpha_verified} 个适用市场全部通过" in quick_advice
    assert f"另外 {alpha_not_applicable} 个由 QVeris 明确标为不支持" in quick_advice


def test_article_selection_facts_match_every_snapshot_row() -> None:
    article = ARTICLE.read_text(encoding="utf-8")
    snapshot = json.loads((MANIFEST.parent / "selection-snapshot.json").read_text())
    aliases = {"Massive Stocks": "Massive"}
    runtime_rows = _markdown_table_rows(article, "| 供应商与 Access Path |")
    pricing_rows = _markdown_table_rows(article, "| Provider / Access Path |")
    market_rows = _markdown_table_rows(article, "通过（2/2）的代表市场")

    for row in snapshot["rows"]:
        provider = aliases.get(row["provider_name"], row["provider_name"])
        access_path = (
            "Native MCP" if row["access_path_type"] == "native_mcp" else "QVeris"
        )
        runtime_row = _provider_row(runtime_rows, provider, access_path)
        metrics = row["gateway_metrics"]
        if metrics["state"] == "measured":
            amount = row["qveris_list_price"]["amount_credits"]
            unit = "credit/call" if amount == 1 else "credits/call"
            runtime = (
                f"{metrics['latency_median_ms']:.0f} ms / "
                f"{amount:g} {unit}"
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
        elif provider != "Massive":
            assert "Evidence insufficient" in pricing_row[1]
            assert "Evidence insufficient" in pricing_row[2]
        else:
            assert "https://massive.com/pricing?product=stocks" in pricing_row[0]
            assert "Stocks Basic Free" in pricing_row[1]

        market_row = _provider_row(market_rows, provider, access_path)
        results = row["market_coverage"]["results"]
        expected = {
            state: {result["market"] for result in results if result["state"] == state}
            for state in ("verified", "provider_negative", "not_applicable")
        }
        published = [
            set()
            if cell == "—"
            else set(re.split("[：:]", cell, maxsplit=1)[0].split(", "))
            for cell in market_row[1:4]
        ]
        assert published == [
            expected["verified"],
            expected["provider_negative"],
            expected["not_applicable"],
        ]


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
