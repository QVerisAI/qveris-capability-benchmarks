"""Acceptance tests for the response self-description probe."""

from __future__ import annotations

from pathlib import Path

from scripts.agent_response_self_description_probe import (
    _determined,
    load_fixture,
)

ROOT = Path(__file__).resolve().parents[2]


def test_ac1_determined_answers_parse() -> None:
    assert _determined("能")
    assert _determined("能，响应里有币种代码。")
    assert not _determined("不能。缺少时区字段。")
    assert not _determined("不能")


def test_ac2_fixture_loads_six_suppliers_and_three_elements() -> None:
    elements, cases = load_fixture(
        ROOT / "scripts/fixtures/fx-response-self-description.yaml"
    )
    assert [element for element, _ in elements] == ["pair", "unit", "time"]
    assert {case.supplier for case in cases} == {
        "Alpha Vantage",
        "Twelve Data",
        "EODHD",
        "波兰国家银行",
        "同花顺 iFinD",
        "融聚汇",
    }
    assert all(case.response_text for case in cases)
