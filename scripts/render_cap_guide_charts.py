#!/usr/bin/env python3
"""Render guide charts from bound evidence files (latest batch only)."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import yaml

try:
    from matplotlib import font_manager

    for font_name in ("PingFang SC", "Arial Unicode MS", "Heiti SC"):
        if any(f.name == font_name for f in font_manager.fontManager.ttflist):
            plt.rcParams["font.sans-serif"] = [font_name]
            break
    plt.rcParams["axes.unicode_minus"] = False
except Exception:
    pass


def _latest_batch(path: Path) -> list[dict]:
    records = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if not records:
        return []
    latest = max(record["recorded_at"] for record in records)
    return [record for record in records if record["recorded_at"] == latest]


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data",
        type=Path,
        default=Path("scripts/fixtures/dividend-chart-data.yaml"),
    )
    parser.add_argument(
        "--direct",
        type=Path,
        default=Path("evidence/private/cap-direct-test.jsonl"),
    )
    parser.add_argument(
        "--param",
        type=Path,
        default=Path("evidence/private/agent-param-fill.jsonl"),
    )
    parser.add_argument(
        "--interpret",
        type=Path,
        default=Path("evidence/private/agent-response-interpretation.jsonl"),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("docs/guides/capability-seo/best-dividend-apis/charts"),
    )
    args = parser.parse_args(argv)

    config = yaml.safe_load(args.data.read_text(encoding="utf-8"))
    suppliers = config["suppliers"]
    market_universe = config["market_universe"]

    direct = _latest_batch(args.direct)
    param = _latest_batch(args.param)
    interpret = _latest_batch(args.interpret)

    latency: dict[str, float] = {}
    cost: dict[str, float] = {}
    for supplier in suppliers:
        cells = [
            record
            for record in direct
            if record["supplier"] == supplier["direct_supplier"]
            and record["latency_ms"] is not None
        ]
        if cells:
            latency[supplier["name"]] = sum(
                record["latency_ms"] for record in cells
            ) / len(cells)
            cost[supplier["name"]] = sum(
                record["cost_credits"] for record in cells
            ) / len(cells)

    param_pass: dict[str, float] = {}
    for supplier in suppliers:
        records = [
            record
            for record in param
            if record["question_id"] == supplier["param_question"]
        ]
        if records:
            param_pass[supplier["name"]] = sum(
                1 for record in records if record["passed"]
            ) / len(records)

    interpret_pass = (
        sum(1 for record in interpret if record["passed"]) / len(interpret)
        if interpret
        else 0.0
    )

    args.output_dir.mkdir(parents=True, exist_ok=True)
    chart_paths: list[str] = []

    # 1. latency vs cost scatter
    names = list(latency)
    colors = {
        "恒生聚源": "#d62728",
        "同花顺 iFinD": "#d62728",
        "Twelve Data": "#1f77b4",
        "Alpha Vantage": "#1f77b4",
        "EODHD": "#1f77b4",
        "Massive": "#2ca02c",
    }
    fig, ax = plt.subplots(figsize=(8, 5))
    for name in names:
        ax.scatter(
            latency[name],
            cost[name],
            s=140,
            color=colors.get(name, "#333333"),
            zorder=3,
        )
        ax.annotate(
            name,
            (latency[name], cost[name]),
            textcoords="offset points",
            xytext=(8, 8),
            fontsize=9,
        )
    ax.set_xlabel("实测平均延迟（ms，2026-08-09）")
    ax.set_ylabel("实测单次费用（QVeris credits）")
    ax.set_title("分红数据 API：延迟与单次费用（本平台 Direct Test 实测）")
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    path = args.output_dir / "chart-latency-cost.png"
    fig.savefig(path, dpi=150)
    plt.close(fig)
    chart_paths.append(path.name)

    # 2. AI param-fill pass rate
    fig, ax = plt.subplots(figsize=(8, 5))
    bar_names = [
        supplier["name"] for supplier in suppliers if supplier["name"] in param_pass
    ]
    values = [param_pass[name] * 100 for name in bar_names]
    bar_colors = [colors.get(name, "#333333") for name in bar_names]
    ax.bar(bar_names, values, color=bar_colors)
    ax.set_ylim(0, 105)
    ax.set_ylabel("AI 入参通过率（%，2 轮）")
    ax.set_title(
        "AI 友好度：入参落参通过率（DeepSeek Flash）；"
        f"出参解读通用样本 {interpret_pass * 100:.0f}%（4/4）"
    )
    for index, value in enumerate(values):
        ax.text(index, value + 3, f"{value:.0f}%", ha="center", fontsize=9)
    fig.tight_layout()
    path = args.output_dir / "chart-ai-friendliness.png"
    fig.savefig(path, dpi=150)
    plt.close(fig)
    chart_paths.append(path.name)

    # 3. market coverage heatmap
    matrix = [
        [market in supplier["markets"] for market in market_universe]
        for supplier in suppliers
    ]
    fig, ax = plt.subplots(figsize=(11, 5))
    ax.imshow(matrix, cmap="Greens", aspect="auto")
    ax.set_xticks(range(len(market_universe)))
    ax.set_xticklabels(market_universe, fontsize=9)
    ax.set_yticks(range(len(suppliers)))
    ax.set_yticklabels([supplier["name"] for supplier in suppliers], fontsize=9)
    cells = [
        (row, col)
        for row in range(len(suppliers))
        for col in range(len(market_universe))
    ]
    for row, col in cells:
        ax.text(
            col,
            row,
            "●" if matrix[row][col] else "○",
            ha="center",
            va="center",
            fontsize=12,
        )
    ax.set_title("分红数据 API 市场覆盖（QVeris 注册表标签 + 官方声明）")
    fig.tight_layout()
    path = args.output_dir / "chart-market-coverage.png"
    fig.savefig(path, dpi=150)
    plt.close(fig)
    chart_paths.append(path.name)

    manifest: dict[str, object] = {
        "charts": {
            path: _digest(args.output_dir / path) for path in chart_paths
        },
        "input_digests": {
            "cap-direct-test": _digest(args.direct),
            "agent-param-fill": _digest(args.param),
            "agent-response-interpretation": _digest(args.interpret),
        },
        "rendered_at": "2026-08-09",
    }
    (args.output_dir / "charts-manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    print(json.dumps(manifest, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
