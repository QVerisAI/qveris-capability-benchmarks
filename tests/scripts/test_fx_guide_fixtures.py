"""Acceptance tests for the FX.SPOT guide fixtures and published artifacts."""

from __future__ import annotations

from pathlib import Path

from scripts.agent_param_fill_probe import load_fixture as load_param_fixture
from scripts.agent_response_interpretation_probe import (
    load_fixture as load_interpret_fixture,
)
from scripts.cap_direct_test_probe import load_fixture as load_direct_fixture

ROOT = Path(__file__).resolve().parents[2]


def test_ac2_fx_direct_test_fixture_loads_all_suppliers() -> None:
    probes = load_direct_fixture(ROOT / "scripts/fixtures/cap-direct-test-fx.yaml")
    suppliers = {probe.supplier for probe in probes}
    assert suppliers == {
        "Alpha Vantage",
        "Twelve Data",
        "EODHD",
        "波兰国家银行",
        "同花顺 iFinD",
        "融聚汇",
    }
    for probe in probes:
        assert len(probe.cases) == 2
        assert sum(case.negative_control for case in probe.cases) == 1
        assert probe.tool_id


def test_ac3_fx_param_fill_fixture_one_question_per_tool() -> None:
    probes = load_param_fixture(ROOT / "scripts/fixtures/agent-param-fill-fx.yaml")
    assert len(probes) == 6
    for contract, questions in probes:
        assert len(questions) == 1
        assert contract.params
        assert any(param.required for param in contract.params)


def test_ac4_fx_interpretation_fixture_has_positive_and_negative() -> None:
    cases = load_interpret_fixture(
        ROOT / "scripts/fixtures/agent-response-interpretation-fx.yaml"
    )
    assert len(cases) == 2
    assert sum(question.negative_control for question, _ in cases) == 1


def test_ac5_article_manifest_and_charts_exist() -> None:
    article = ROOT / "docs/guides/best-forex-api-apis.md"
    manifest = ROOT / "docs/guides/capability-seo/best-forex-api-apis/manifest.yaml"
    chart_dir = ROOT / "docs/guides/capability-seo/best-forex-api-apis/charts"
    assert article.is_file()
    assert manifest.is_file()
    for name in (
        "chart-latency-cost.png",
        "chart-ai-friendliness.png",
        "chart-market-coverage.png",
    ):
        assert (chart_dir / name).is_file()


def test_ac7_article_keeps_internal_ids_and_aggregate_ratings_out() -> None:
    article = (ROOT / "docs/guides/best-forex-api-apis.md").read_text(encoding="utf-8")
    for forbidden in ("FX.SPOT", "tool_id", "总分", "综合评分", "grade"):
        assert forbidden not in article, f"article must not expose {forbidden}"
