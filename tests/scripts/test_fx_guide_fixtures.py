"""Acceptance tests for the FX.SPOT guide fixtures and published artifacts."""

from __future__ import annotations

import json
from pathlib import Path

import yaml

from scripts.agent_error_recovery_probe import load_fixture as load_recovery_fixture
from scripts.agent_param_fill_probe import load_fixture as load_param_fixture
from scripts.agent_response_interpretation_probe import (
    load_fixture as load_interpret_fixture,
)
from scripts.agent_response_self_description_probe import (
    load_fixture as load_self_description_fixture,
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
        "融聚汇",
    }
    assert {probe.access_path_id for probe in probes} == {
        "alpha-vantage-fx-spot-qveris",
        "twelve-data-fx-spot-qveris",
        "eodhd-fx-spot-qveris",
        "rongjuhui-hkd-reference-rate",
    }, "AC2 every Direct fixture must bind one explicit Access Path"
    for probe in probes:
        assert len(probe.cases) == 2
        assert sum(case.negative_control for case in probe.cases) == 1
        assert probe.tool_id


def test_ac3_fx_param_fill_fixture_two_questions_per_tool() -> None:
    probes = load_param_fixture(ROOT / "scripts/fixtures/agent-param-fill-fx.yaml")
    assert len(probes) == 4
    for contract, questions in probes:
        assert contract.provider_id, "AC3 Agent fixture must retain provider identity"
        assert contract.access_path_id, (
            "AC3 Agent fixture must retain Access Path identity"
        )
        assert contract.tool_id != "cn_financial_pro.fx_rates.v1", (
            "AC3 legacy QVeris iFinD evidence must not masquerade as native MCP"
        )
        assert len(questions) == 2
        assert contract.params
        assert any(param.required for param in contract.params)
        assert all(question.difficulty for question in questions)


def test_ac3_all_agent_fixtures_bind_registered_access_paths() -> None:
    for path in sorted((ROOT / "scripts/fixtures").glob("agent-param-fill-*.yaml")):
        probes = load_param_fixture(path, ROOT / "providers")
        assert all(
            contract.provider_id and contract.access_path_id for contract, _ in probes
        )
    for path in sorted((ROOT / "scripts/fixtures").glob("agent-error-recovery-*.yaml")):
        probes = load_recovery_fixture(path, ROOT / "providers")
        assert all(
            contract.provider_id and contract.access_path_id for contract, _ in probes
        )


def test_ac4_fx_interpretation_fixture_has_positive_and_negative() -> None:
    cases = load_interpret_fixture(
        ROOT / "scripts/fixtures/agent-response-interpretation-fx.yaml"
    )
    assert len(cases) == 3
    assert sum(question.negative_control for question, _ in cases) == 2


def test_ac4b_fx_error_recovery_fixture_loads() -> None:
    probes = load_recovery_fixture(
        ROOT / "scripts/fixtures/agent-error-recovery-fx.yaml"
    )
    assert len(probes) == 3
    for contract, questions in probes:
        assert contract.provider_id, (
            "AC4 recovery fixture must retain provider identity"
        )
        assert contract.access_path_id, (
            "AC4 recovery fixture must retain Access Path identity"
        )
        assert contract.tool_id != "cn_financial_pro.fx_rates.v1", (
            "AC4 legacy QVeris iFinD recovery evidence must not be relabeled"
        )
        assert len(questions) == 1
        assert questions[0].failure_response
        assert questions[0].expected_retry_params
        assert contract.params


def test_ac5_article_manifest_and_charts_exist() -> None:
    article = ROOT / "docs/guides/best-forex-api-apis.md"
    manifest = ROOT / "docs/guides/capability-seo/best-forex-api-apis/manifest.yaml"
    chart_dir = ROOT / "docs/guides/capability-seo/best-forex-api-apis/charts"
    assert article.is_file()
    assert manifest.is_file()
    for name in (
        "chart-latency-cost.png",
        "chart-ai-difficulty.png",
        "chart-ai-recovery.png",
        "chart-market-coverage.png",
    ):
        assert (chart_dir / name).is_file()
    chart_manifest = json.loads(
        (chart_dir / "charts-manifest.json").read_text(encoding="utf-8")
    )
    assert set(chart_manifest["input_digests"]) == {
        "chart-data",
        "released-observations",
    }
    publication_manifest = yaml.safe_load(manifest.read_text(encoding="utf-8"))
    assert all(
        path["evidence_state"] == "evidence_insufficient"
        for path in publication_manifest["access_paths"]
    )


def test_ac5_article_separates_access_paths_and_price_facts() -> None:
    article = (ROOT / "docs/guides/best-forex-api-apis.md").read_text(encoding="utf-8")
    assert "QVeris Access Path" in article
    assert "Native Access Path" in article
    assert "供应商官网价格" in article
    assert "QVeris 路径观测费用" in article
    assert "证据不足" in article
    assert "在 QVeris 中试用](https://qveris.ai/providers/ths_ifind)" not in article
    assert "在 QVeris 中试用](https://qveris.ai/providers/nbp_pl)" not in article
    assert "Harbor" not in article


def test_ac5_released_fx_observations_keep_paths_distinct() -> None:
    document = yaml.safe_load(
        (ROOT / "scripts/fixtures/fx-released-observations.yaml").read_text(
            encoding="utf-8"
        )
    )
    observations = document["access_path_observations"]
    keys = {(row["provider_id"], row["access_path_id"]) for row in observations}
    assert len(keys) == len(observations)
    assert {
        ("ifind", "ifind-native-mcp"),
        ("nbp-pl", "nbp-pl-exchange-rates-native"),
    } <= keys
    for row in observations:
        assert row["evidence_state"] == "evidence_insufficient"
        assert "latency_ms" not in row
        assert "qveris_credits" not in row
        assert "direct_test" not in row


def test_ac5b_fx_dialect_tolerance_fixture_loads() -> None:
    import yaml

    document = yaml.safe_load(
        (ROOT / "scripts/fixtures/fx-dialect-tolerance.yaml").read_text(
            encoding="utf-8"
        )
    )
    assert document["capability"] == "FX.SPOT"
    assert len(document["suppliers"]) == 4
    for supplier in document["suppliers"]:
        assert supplier["provider_id"]
        assert supplier["access_path_id"]
        assert supplier["variants"]
        for variant in supplier["variants"]:
            assert variant["outcome"] in {
                "accepted",
                "accepted_empty",
                "rejected_error",
            }


def test_ac5c_fx_self_description_fixture_loads() -> None:
    elements, cases = load_self_description_fixture(
        ROOT / "scripts/fixtures/fx-response-self-description.yaml"
    )
    assert len(elements) == 3
    assert len(cases) == 4
    assert all(case.provider_id and case.access_path_id for case in cases), (
        "AC5 response observations must retain Access Path identity"
    )
    assert all(
        case.supplier not in {"同花顺 iFinD", "波兰国家银行"} for case in cases
    ), "AC5 legacy gateway responses cannot stand in for native evidence"


def test_ac7_article_keeps_internal_ids_and_aggregate_ratings_out() -> None:
    article = (ROOT / "docs/guides/best-forex-api-apis.md").read_text(encoding="utf-8")
    for forbidden in ("FX.SPOT", "tool_id", "总分", "综合评分", "grade"):
        assert forbidden not in article, f"article must not expose {forbidden}"
