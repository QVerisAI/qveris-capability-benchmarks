"""Acceptance tests for the funnel article skeleton generator.

Tests use inline fixture records so they do not depend on gitignored
evidence/private files and can run in CI.
"""

from __future__ import annotations

from scripts.render_guide_article import (
    aggregate_records,
    load_chart_data,
    render_article,
    render_main_table,
)


def _chart() -> dict:
    from pathlib import Path

    return load_chart_data(
        Path(__file__).resolve().parents[2]
        / "scripts"
        / "fixtures"
        / "dividend-chart-data.yaml"
    )


def _sample_data() -> dict:
    """Inline probe records mirroring the dividends evidence shape."""
    return {
        "direct_test": {
            "twelve-data": {
                "passed": 4,
                "total": 4,
                "avg_latency_ms": 414,
                "success_call_credits": 2.37,
            },
            "ifind": {
                "passed": 4,
                "total": 4,
                "avg_latency_ms": 419,
                "success_call_credits": 1.0,
            },
        },
        "param_fill": {
            "twelve-data": {"passed": 2, "total": 2},
            "ifind": {"passed": 2, "total": 2},
        },
        "error_recovery": {
            "twelve-data": {"passed": 2, "total": 2},
            "ifind": {"passed": 0, "total": 2},
        },
        "interpretation": {
            "dividend-aapl-latest": {"passed": 2, "total": 2},
        },
        "self_description": {
            "twelve-data": {
                "total": 6,
                "ex_date": "2/2",
                "amount": "2/2",
                "currency": "2/2",
            },
            "ifind": {
                "total": 3,
                "ex_date": "0/2",
                "amount": "2/2",
                "currency": "1/2",
            },
        },
    }


def test_main_table_lists_suppliers() -> None:
    table = render_main_table(_sample_data(), _chart())
    names = [
        "同花顺 iFinD",
        "恒生聚源",
        "Twelve Data",
        "Alpha Vantage",
        "EODHD",
        "Massive",
    ]
    for name in names:
        assert any(line.startswith(f"| {name} ") for line in table.splitlines()), (
            f"main table missing supplier: {name}"
        )


def test_ai_dimensions_fill_correctly() -> None:
    table = render_main_table(_sample_data(), _chart())
    row = next(line for line in table.splitlines() if "Twelve Data" in line)
    assert "2/2 | 2/2 | 6/6" in row, f"Twelve Data row mismatch: {row}"
    row = next(line for line in table.splitlines() if "同花顺 iFinD" in line)
    assert "2/2 | 0/2 | 3/6" in row, f"iFinD row mismatch: {row}"


def test_aggregate_records_groups_by_provider() -> None:
    records = [
        {"provider_id": "a", "passed": True},
        {"provider_id": "a", "passed": False},
        {"provider_id": "b", "passed": True},
    ]
    agg = aggregate_records(records, provider_key="provider_id")
    assert agg["a"] == {"passed": 1, "total": 2}
    assert agg["b"] == {"passed": 1, "total": 1}


def test_article_skeleton_has_todo_placeholders() -> None:
    article = render_article(_sample_data(), _chart(), "分红数据", "2026-08-10")
    assert "<!-- TODO" in article, "editorial sections must keep TODO placeholders"
    assert "## 快速结论" in article
    assert "## 供应商深度解析" in article
    assert "## 更正与复测" in article


def test_article_contains_date_anchors() -> None:
    article = render_article(_sample_data(), _chart(), "分红数据", "2026-08-10")
    assert "2026-08-10" in article
