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
        "--recovery",
        type=Path,
        default=Path("evidence/private/agent-error-recovery.jsonl"),
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
    guide_label = config.get("guide_label", "分红数据 API")
    edition_date = config.get("edition_date", "2026-08-09")

    direct = _latest_batch(args.direct)
    param = _latest_batch(args.param)
    interpret = _latest_batch(args.interpret)
    try:
        recovery = _latest_batch(args.recovery)
    except FileNotFoundError:
        recovery = []

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

    def _question_ids(supplier: dict[str, object]) -> list[str]:
        questions = supplier.get("param_questions") or []
        if questions:
            return list(questions)
        legacy = supplier.get("param_question")
        return [legacy] if legacy else []

    difficulty_pass: dict[str, dict[str, tuple[int, int]]] = {}
    for supplier in suppliers:
        records = [
            record
            for record in param
            if record["question_id"] in _question_ids(supplier)
        ]
        if records:
            per_level: dict[str, list[dict]] = {}
            for record in records:
                per_level.setdefault(record.get("difficulty", "L1"), []).append(record)
            difficulty_pass[supplier["name"]] = {
                level: (
                    sum(1 for record in rows if record["passed"]),
                    len(rows),
                )
                for level, rows in per_level.items()
            }

    interpret_ok = sum(1 for record in interpret if record["passed"])
    interpret_total = len(interpret)

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
        "波兰国家银行": "#2ca02c",
        "融聚汇": "#9467bd",
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
    ax.set_xlabel(f"实测平均延迟（ms，{edition_date}）")
    ax.set_ylabel("实测单次费用（QVeris credits）")
    ax.set_title(f"{guide_label}：延迟与单次费用（本平台 Direct Test 实测）")
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    path = args.output_dir / "chart-latency-cost.png"
    fig.savefig(path, dpi=150)
    plt.close(fig)
    chart_paths.append(path.name)

    # 2. AI param-fill pass rate by difficulty
    fig, ax = plt.subplots(figsize=(9, 5))
    levels = ["L1", "L2", "L3", "L4"]
    for supplier in suppliers:
        name = supplier["name"]
        series = difficulty_pass.get(name, {})
        xs = [level for level in levels if level in series]
        ys = [series[level][0] / series[level][1] * 100 for level in xs]
        ax.plot(
            xs,
            ys,
            marker="o",
            label=name,
            color=colors.get(name, "#333333"),
        )
        for x, y in zip(xs, ys, strict=True):
            ax.annotate(
                f"{y:.0f}%",
                (x, y),
                textcoords="offset points",
                xytext=(0, 8),
                fontsize=8,
            )
    ax.set_ylim(0, 110)
    ax.set_ylabel("AI 入参通过率（%，2 轮）")
    ax.set_xlabel("题目难度（契约认知负担）")
    ax.set_title(
        f"{guide_label} AI 友好度：入参通过率按难度（DeepSeek Flash）；"
        f"出参解读 {interpret_ok}/{interpret_total}"
    )
    ax.legend(fontsize=8, loc="lower left")
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    path = args.output_dir / "chart-ai-difficulty.png"
    fig.savefig(path, dpi=150)
    plt.close(fig)
    chart_paths.append(path.name)

    # 3. error-recovery pass rate
    recovery_pass: dict[str, float] = {}
    for supplier in suppliers:
        questions = supplier.get("recovery_questions") or []
        records = [record for record in recovery if record["question_id"] in questions]
        if records:
            recovery_pass[supplier["name"]] = sum(
                1 for record in records if record["passed"]
            ) / len(records)
    fig, ax = plt.subplots(figsize=(8, 5))
    bar_names = [
        supplier["name"] for supplier in suppliers if supplier["name"] in recovery_pass
    ]
    values = [recovery_pass[name] * 100 for name in bar_names]
    ax.bar(bar_names, values, color=[colors.get(name, "#333333") for name in bar_names])
    ax.set_ylim(0, 105)
    ax.set_ylabel("失败自愈率（%，2 轮）")
    ax.set_title(f"{guide_label} AI 友好度：失败自愈率（错误解读 + 修正重试）")
    for index, value in enumerate(values):
        ax.text(index, value + 3, f"{value:.0f}%", ha="center", fontsize=9)
    fig.tight_layout()
    path = args.output_dir / "chart-ai-recovery.png"
    fig.savefig(path, dpi=150)
    plt.close(fig)
    chart_paths.append(path.name)

    # 4. market coverage heatmap
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
    ax.set_title(f"{guide_label} 市场覆盖（实测 + 工具契约声明）")
    fig.tight_layout()
    path = args.output_dir / "chart-market-coverage.png"
    fig.savefig(path, dpi=150)
    plt.close(fig)
    chart_paths.append(path.name)

    manifest: dict[str, object] = {
        "charts": {path: _digest(args.output_dir / path) for path in chart_paths},
        "input_digests": {
            "cap-direct-test": _digest(args.direct),
            "agent-param-fill": _digest(args.param),
            "agent-response-interpretation": _digest(args.interpret),
        },
        "rendered_at": edition_date,
    }
    (args.output_dir / "charts-manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    print(json.dumps(manifest, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
