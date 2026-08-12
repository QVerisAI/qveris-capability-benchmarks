from __future__ import annotations

import hashlib
import inspect
import json
import platform
import re
from pathlib import Path

import pytest
import yaml
from PIL import Image

from qveris_bench.profiles.selection import build_selection_snapshot
from scripts.render_cap_guide_charts import (
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
    "capability-seo/best-dividend-apis/charts/dividend-runtime-tradeoff.png",
    "capability-seo/best-dividend-apis/charts/dividend-market-coverage.png",
)
MANIFEST_EVIDENCE_CHARTS = tuple(f"docs/guides/{target}" for target in EVIDENCE_CHARTS)


def test_english_publication_contract(tmp_path: Path) -> None:
    article = ARTICLE.read_text(encoding="utf-8")
    manifest = yaml.safe_load(MANIFEST.read_text(encoding="utf-8"))
    seo = manifest["seo"]

    assert re.search(r"[\u4e00-\u9fff]", article) is None
    assert article.splitlines()[0] == f"# {seo['title']}"
    assert 40 <= len(seo["title"]) <= 60
    assert 150 <= len(seo["meta_description"]) <= 160
    assert seo["primary_keyword"].lower() in seo["title"].lower()
    for keyword in seo["secondary_keywords"]:
        assert keyword.lower() in article.lower()
    assert manifest["publication_policy"]["required_sections"] == [
        "Results at a glance",
        "How developers should choose",
        "Evidence and provider differences",
        "What AI Agent builders should verify",
        "Method, reproduction, and contribution",
        "Limitations, disclosures, and corrections",
        "FAQ",
    ]
    assert manifest["publication_policy"]["public_outcomes"] == [
        "Sample passed",
        "Sample did not pass",
        "Evidence insufficient",
        "Not tested: explicitly not applicable",
    ]

    snapshot = MANIFEST.parent / "selection-snapshot.json"
    rendered = render_selection_tradeoff(snapshot, tmp_path)
    market = rendered["data"]["market_coverage"]
    assert market["title"] == (
        "Dividend Event results: 9 representative markets × 6 Access Paths"
    )
    assert {row["provider"] for row in market["rows"]} >= {"Hang Seng", "iFinD"}
    assert (
        re.search(r"[\u4e00-\u9fff]", inspect.getsource(render_selection_tradeoff))
        is None
    )


def test_article_is_bound_to_dividend_release() -> None:
    article = ARTICLE.read_text(encoding="utf-8")

    assert "dividend-events-2026-q3-v1" in article
    assert RELEASE_DIGEST in article
    assert "three times" in article
    assert "36 live calls" in article
    assert "iFinD](" in article
    assert "(Native MCP)" in article
    assert "Sample did not pass" in article
    assert "https://qveris.ai/providers/ths_ifind" not in article
    assert "AI-friendly rating" not in article
    assert "Direct Test 4/4" not in article


def test_article_uses_reader_facing_outcomes_and_one_decision_flow() -> None:
    article = ARTICLE.read_text(encoding="utf-8")

    for internal_term in ("Qualified", "Not qualified", "Agent-friendly score"):
        assert internal_term not in article
    for public_state in (
        "Sample passed",
        "Sample did not pass",
        "Not tested: explicitly not applicable",
    ):
        assert public_state in article

    headings = [
        "## Results at a glance",
        "## How developers should choose",
        "## Evidence and provider differences",
        "## What AI Agent builders should verify",
        "## Method, reproduction, and contribution",
        "## Limitations, disclosures, and corrections",
        "## FAQ",
    ]
    positions = [article.index(heading) for heading in headings]
    assert positions == sorted(positions)
    assert "## Five things to do when integrating an AI Agent" not in article


def test_article_publishes_inspect_list_prices_not_discounted_account_costs() -> None:
    article = ARTICLE.read_text(encoding="utf-8")
    overview_rows = _markdown_table_rows(article, "| Provider and Access Path |")
    expected = {
        "Hang Seng": "1 credit/call",
        "Twelve Data": "2.37 credits/call",
        "Alpha Vantage": "0 credits/call",
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
    assert "public QVeris Inspect price" in article
    assert "actual charge to the test account" in article
    assert "https://massive.com/pricing?product=stocks" in article
    assert "Stocks Basic Free" in article


def test_article_explains_market_samples_and_evidence_heatmap() -> None:
    article = ARTICLE.read_text(encoding="utf-8")

    for phrase in (
        "representative market sample results",
        "passed (2/2)",
        "did not pass (0/2)",
        "not tested: explicitly not applicable",
        "does not prove that the provider does not support the market",
        "does not mean every historical record is complete",
    ):
        assert phrase in article
    for confusing_term in (
        "identity blocked",
        "not independently measured",
        "stockobject",
        "stockcode",
        "successor release",
        "extractor",
    ):
        assert confusing_term not in article
    assert "dividend-evidence-heatmap.png" not in article
    retired = MANIFEST.parent / "charts"
    assert not (retired / "dividend-evidence-heatmap.png").exists()
    assert not (retired / "evidence-matrix-manifest.json").exists()


def test_article_uses_only_approved_published_related_guides() -> None:
    article = ARTICLE.read_text(encoding="utf-8")
    manifest = yaml.safe_load(MANIFEST.read_text(encoding="utf-8"))

    for target in (
        "_shared/benchmark-methodology.md",
        "market-data-api-for-ai-agents",
        "ai-stock-research-agent",
        "stock-api-free-comparison",
    ):
        assert target not in article
    related_guides = manifest["seo"]["related_guides"]
    assert related_guides == [
        {
            "anchor": "Capability Discovery for AI Agents",
            "url": "https://qveris.ai/guides/capability-discovery-ai-agents/",
        },
        {
            "anchor": "QVeris CLI guide",
            "url": "https://qveris.ai/guides/qveris-cli/",
        },
    ]
    for guide in related_guides:
        assert f"[{guide['anchor']}]({guide['url']})" in article


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
    snapshot = json.loads((MANIFEST.parent / "selection-snapshot.json").read_text())
    agent_rows = _markdown_table_rows(
        article, "| Provider and Access Path | Required event fields |"
    )

    assert "## What AI Agent builders should verify" in article
    for signal in (
        "Required event fields",
        "Security identity",
        "Invalid symbol",
        "Currency in response",
        "Additional event dates",
        "Parameter clarity, pagination, and Agent Trial",
    ):
        assert signal in article
    assert "AI-friendly rating" not in article
    assert "Agent total score" not in article
    identity_text = {
        "hangseng": "Returned security code matched the requested symbol",
        "ifind": "No response security code was available to cross-check",
        "twelve-data": (
            "Published sample does not prove the response identified `AAPL`"
        ),
        "alpha-vantage": (
            "Published sample does not prove the response identified `AAPL`"
        ),
        "eodhd": "Published sample does not prove the response identified `AAPL`",
        "massive-stocks": (
            "Published sample does not prove the response identified `AAPL`"
        ),
    }
    required_fields = {
        "hangseng": "CN sample 2/2",
        "ifind": "Missing single-event amount meaning and ex-dividend date",
        "twelve-data": "3/3",
        "alpha-vantage": "3/3",
        "eodhd": "3/3",
        "massive-stocks": "3/3",
    }
    currency_text = {
        "hangseng": "Not returned in this sample",
        "ifind": "Not published in this sample",
        "twelve-data": "`USD`",
        "alpha-vantage": "Not returned in this sample",
        "eodhd": "Not returned in this sample",
        "massive-stocks": "`USD`",
    }
    additional_dates = {
        "hangseng": "Declaration, record, and payment dates",
        "ifind": "No single-event date set",
        "twelve-data": "Only ex-dividend date in this sample",
        "alpha-vantage": "Declaration, record, and payment dates",
        "eodhd": "Only ex-dividend date in this sample",
        "massive-stocks": "Declaration, record, and payment dates",
    }
    for snapshot_row in snapshot["rows"]:
        provider = _article_provider_name(snapshot_row)
        access_path = (
            "Native MCP"
            if snapshot_row["access_path_type"] == "native_mcp"
            else "QVeris"
        )
        article_row = _provider_row(agent_rows, provider, access_path)
        provider_id = snapshot_row["provider_id"]
        invalid = snapshot_row["agent_interface"]["invalid_input_handling"]
        assert article_row[1] == required_fields[provider_id]
        assert article_row[2] == identity_text[provider_id]
        expected_invalid = f"Handled correctly {invalid['passed']}/{invalid['total']}"
        assert article_row[3] == expected_invalid
        assert article_row[4] == currency_text[provider_id]
        assert article_row[5] == additional_dates[provider_id]


def test_article_evidence_charts_are_declared_and_valid_image() -> None:
    article = ARTICLE.read_text(encoding="utf-8")
    manifest = yaml.safe_load(MANIFEST.read_text(encoding="utf-8"))

    assert manifest["artifacts"]["charts"] == list(MANIFEST_EVIDENCE_CHARTS)
    for target in EVIDENCE_CHARTS:
        assert target in article
        path = ARTICLE.parent / target
        assert path.is_file()
        with Image.open(path) as chart:
            assert chart.width >= 1600
            assert chart.height >= 900
            assert chart.width > chart.height
    assert "complete event date set" not in article
    assert "date-timeline.svg" not in article
    assert "dividend-api-evidence-matrix.svg" not in article


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
    if platform.system() == "Linux":
        assert generated["charts"] == committed["charts"]
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
        if platform.system() == "Linux":
            assert (tmp_path / chart_name).read_bytes() == (
                committed_dir / chart_name
            ).read_bytes()
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
        "Dividend Event results: 9 representative markets × 6 Access Paths"
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
    assert "× 7 Access Paths" in rendered["data"]["market_coverage"]["title"]


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
    market_section = article.split("### Representative samples across nine markets", 1)[
        1
    ].split("### Provider-by-provider analysis", 1)[0]
    chart_path = "capability-seo/best-dividend-apis/charts/dividend-market-coverage.png"

    assert f"]({chart_path})]({chart_path})" in market_section
    assert "Green means the fixed representative symbol" in market_section


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
    supplement = ROOT / manifest["artifacts"]["official_pricing_supplement"]
    assert manifest["official_pricing_supplement"]["digest"] == (
        f"sha256:{hashlib.sha256(supplement.read_bytes()).hexdigest()}"
    )
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
        "Median QVeris gateway latency",
        "public QVeris Inspect price",
        "official pricing",
        "representative market sample",
        "nine markets",
        "parameter clarity",
        "schema stability",
        "error recovery",
    ):
        assert phrase in article
    assert "491 ms / 2.37 credits/call" in article
    assert "576 ms / 0 credits/call" in article
    assert "779 ms / 2.81 credits/call" in article
    assert "861 ms / 1 credit/call" in article
    assert "aggregate AI-friendly rating" not in article
    assert "verified global market coverage" not in article


def test_article_publishes_released_market_coverage_near_the_decision_table() -> None:
    article = ARTICLE.read_text(encoding="utf-8")
    snapshot = json.loads((MANIFEST.parent / "selection-snapshot.json").read_text())
    overview_rows = _markdown_table_rows(article, "| Provider and Access Path |")
    market_rows = _markdown_table_rows(article, "Representative markets passed (2/2)")

    assert (
        "7 markets passed (2/2)" in _provider_row(overview_rows, "EODHD", "QVeris")[4]
    )
    assert "CN passed (2/2)" in _provider_row(overview_rows, "Hang Seng", "QVeris")[4]
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
    hangseng_market_row = _provider_row(market_rows, "Hang Seng", "QVeris")
    assert hangseng_market_row[1] == "CN"
    assert "66 live calls" in article
    assert "other 54 retain an explicit not-applicable reason" in article


def test_article_summary_is_exactly_bound_to_base_and_market_releases() -> None:
    article = ARTICLE.read_text(encoding="utf-8")
    snapshot = json.loads((MANIFEST.parent / "selection-snapshot.json").read_text())
    overview_rows = _markdown_table_rows(article, "| Provider and Access Path |")
    expected_base = {
        "Hang Seng": "**CN sample passed:**",
        "iFinD": "**Sample did not pass:**",
        "Twelve Data": "**Sample passed:**",
        "Alpha Vantage": "**Sample passed:**",
        "EODHD": "**Sample passed:**",
        "Massive": "**Sample passed:**",
    }
    for row in snapshot["rows"]:
        provider = _article_provider_name(row)
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
            assert f"{verified} applicable markets passed (2/2)" in overview[4]
        elif provider in {"EODHD", "Twelve Data"}:
            assert f"{verified} markets passed (2/2)" in overview[4]
        elif provider == "Hang Seng":
            assert "CN passed (2/2)" in overview[4]
        assert (
            applicable
            + sum(
                result["state"] == "not_applicable"
                for result in row["market_coverage"]["results"]
            )
            == 9
        )
    for internal_detail in (
        "stockobject",
        "stockcode",
        "successor release",
        "extractor",
    ):
        assert internal_detail not in article

    quick_advice = article.split("> **Quick recommendation:**", 1)[1].split("\n", 1)[0]
    assert "through the tested qveris access paths" in quick_advice.lower()
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
    assert f"EODHD passed {eodhd_verified} markets" in quick_advice
    assert f"Twelve Data passed {twelve_verified}" in quick_advice
    assert f"Alpha Vantage passed all {alpha_verified} markets" in quick_advice
    assert (
        f"other {alpha_not_applicable} explicitly unsupported markets" in quick_advice
    )


def test_article_selection_facts_match_every_snapshot_row() -> None:
    article = ARTICLE.read_text(encoding="utf-8")
    snapshot = json.loads((MANIFEST.parent / "selection-snapshot.json").read_text())
    runtime_rows = _markdown_table_rows(article, "| Provider and Access Path |")
    pricing_rows = _markdown_table_rows(article, "| Provider / Access Path |")
    market_rows = _markdown_table_rows(article, "Representative markets passed (2/2)")

    for row in snapshot["rows"]:
        provider = _article_provider_name(row)
        access_path = (
            "Native MCP" if row["access_path_type"] == "native_mcp" else "QVeris"
        )
        runtime_row = _provider_row(runtime_rows, provider, access_path)
        metrics = row["gateway_metrics"]
        if metrics["state"] == "measured":
            amount = row["qveris_list_price"]["amount_credits"]
            unit = "credit/call" if amount == 1 else "credits/call"
            runtime = f"{metrics['latency_median_ms']:.0f} ms / {amount:g} {unit}"
            assert runtime in runtime_row[2]
        else:
            assert "Not applicable" in runtime_row[2]

        pricing_row = _provider_row(pricing_rows, provider, access_path)
        pricing = row["official_pricing"]
        if pricing["state"] == "declared":
            assert pricing["pricing_url"] in pricing_row[0]
            assert pricing["free_tier"] in pricing_row[1]
            assert pricing["paid_plans"] in pricing_row[2]
            if row["provider_id"] == "ifind":
                overview_plan = pricing["paid_plans"].split(";", 1)[0]
                assert overview_plan in runtime_row[3]
        else:
            assert "Evidence insufficient" in pricing_row[1]
            assert "Evidence insufficient" in pricing_row[2]

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

    measured = [
        result
        for row in snapshot["rows"]
        for result in row["market_coverage"]["results"]
        if result["state"] != "not_applicable"
    ]
    totals = {result["total_rounds"] for result in measured}
    assert len(totals) == 1
    total = totals.pop()
    assert (
        f"| Provider / Access Path | Representative markets passed ({total}/{total})"
        in article
    )
    assert f"| Representative sample did not pass (0/{total})" in article


def test_article_price_ranking_and_billing_scope_come_from_snapshot() -> None:
    article = ARTICLE.read_text(encoding="utf-8")
    snapshot = json.loads((MANIFEST.parent / "selection-snapshot.json").read_text())
    prices = {
        row["provider_name"]: row["qveris_list_price"]["amount_credits"]
        for row in snapshot["rows"]
        if row["qveris_list_price"]["state"] == "declared"
    }
    minimum = min(prices.values())
    lowest = sorted(name for name, amount in prices.items() if amount == minimum)
    assert lowest == ["Alpha Vantage"]
    assert "Alpha Vantage had the lowest Inspect price at 0 credits/call" in article
    assert "followed by Hang Seng and Massive at 1 credit/call" in article
    assert "does not use account billing in its tables or charts" in article


def test_article_market_totals_are_bound_to_release_and_snapshot() -> None:
    article = ARTICLE.read_text(encoding="utf-8")
    manifest = yaml.safe_load(MANIFEST.read_text(encoding="utf-8"))
    market = manifest["market_coverage_release"]
    snapshot = json.loads((MANIFEST.parent / "selection-snapshot.json").read_text())
    provider_count = len({row["provider_id"] for row in snapshot["rows"]})
    access_path_count = len(snapshot["rows"])
    total_calls = (
        manifest["release"]["public_evidence_records"]
        + market["public_evidence_records"]
    )
    assert article.splitlines()[0] == (
        f"# Best Dividend APIs for Developers in 2026: {provider_count} Providers"
    )
    assert f"{total_calls} live calls" in manifest["seo"]["meta_description"]
    assert manifest["seo"]["meta_description"].startswith(
        f"Compare {access_path_count} dividend API Access Paths"
    )
    assert f"We made {total_calls} live calls" in article
    lead = "\n".join(article.splitlines()[2:9])
    assert "Through the tested QVeris Access Paths" in lead
    assert "produced usable US Dividend Events" not in lead
    assert f"{market['public_evidence_records']} live calls" in article
    assert f"{market['planned_cells']} planned test cells" in article
    not_applicable = market["planned_cells"] - market["applicable_cells"]
    assert f"other {not_applicable} retain an explicit not-applicable reason" in article


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


def _article_provider_name(row: dict[str, object]) -> str:
    aliases = {
        "hangseng": "Hang Seng",
        "ifind": "iFinD",
        "massive-stocks": "Massive",
    }
    return aliases.get(str(row["provider_id"]), str(row["provider_name"]))


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
