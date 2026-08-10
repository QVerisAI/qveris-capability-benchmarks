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
from matplotlib.colors import ListedColormap

from scripts.chart_metrics import direct_metrics_by_access_path

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
    parser.add_argument("--released", type=Path)
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
    observation_date = config.get("observation_date", edition_date)

    released: list[dict] = []
    if args.released:
        released = yaml.safe_load(args.released.read_text(encoding="utf-8"))[
            "access_path_observations"
        ]
        direct = [
            {
                **record,
                "cost_credits": record.get("qveris_credits"),
            }
            for record in released
            if record.get("evidence_state") == "released"
        ]
        param = []
        recovery = []
    else:
        direct = _latest_batch(args.direct)
        param = _latest_batch(args.param)
        try:
            recovery = _latest_batch(args.recovery)
        except FileNotFoundError:
            recovery = []

    latency: dict[str, float] = {}
    cost: dict[str, float] = {}
    path_metrics = direct_metrics_by_access_path(direct, suppliers)
    for supplier in suppliers:
        key = (supplier["provider_id"], supplier["access_path_id"])
        metrics = path_metrics[key]
        label = supplier.get("chart_label", supplier["name"])
        if metrics["latency_ms"] is not None:
            latency[label] = metrics["latency_ms"]
        if metrics["cost_credits"] is not None:
            cost[label] = metrics["cost_credits"]

    def _question_ids(supplier: dict[str, object]) -> list[str]:
        questions = supplier.get("param_questions") or []
        if questions:
            return list(questions)
        legacy = supplier.get("param_question")
        return [legacy] if legacy else []

    parameter_clarity: dict[str, tuple[int, int]] = {}
    if released:
        released_by_path = {
            (record["provider_id"], record["access_path_id"]): record
            for record in released
        }
        for supplier in suppliers:
            record = released_by_path.get(
                (supplier["provider_id"], supplier["access_path_id"]), {}
            )
            observation = record.get("parameter_clarity")
            if observation and "passed" in observation:
                parameter_clarity[supplier["name"]] = (
                    observation["passed"],
                    observation["total"],
                )
    else:
        for supplier in suppliers:
            records = [
                record
                for record in param
                if record["question_id"] in _question_ids(supplier)
            ]
            if records:
                parameter_clarity[supplier["name"]] = (
                    sum(1 for record in records if record["passed"]),
                    len(records),
                )

    args.output_dir.mkdir(parents=True, exist_ok=True)
    chart_paths: list[str] = []

    # 1. latency vs cost scatter
    names = [name for name in latency if name in cost]
    provider_colors = {
        "Alpha Vantage": "#143F74",
        "Twelve Data": "#2F78AD",
        "EODHD": "#6EB0C2",
        "融聚汇": "#8E6BBE",
    }
    fig, ax = plt.subplots(figsize=(8, 5))
    for name in names:
        ax.scatter(
            latency[name],
            cost[name],
            s=140,
            color=provider_colors.get(name, "#143F74"),
            zorder=3,
        )
        ax.annotate(
            name,
            (latency[name], cost[name]),
            textcoords="offset points",
            xytext=(8, 8),
            fontsize=9,
        )
    ax.set_xlabel(f"实测平均延迟（ms，{observation_date}）")
    ax.set_ylabel("实测单次费用（QVeris credits）")
    ax.set_title(f"{guide_label}：QVeris Access Path 延迟与观测费用")
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    path = args.output_dir / "chart-latency-cost.png"
    fig.savefig(path, dpi=150)
    plt.close(fig)
    chart_paths.append(path.name)

    # 2. parameter clarity
    fig, ax = plt.subplots(figsize=(9, 5))
    param_names = [
        supplier["name"]
        for supplier in suppliers
        if supplier["name"] in parameter_clarity
    ]
    param_values = [
        parameter_clarity[name][0] / parameter_clarity[name][1] * 100
        for name in param_names
    ]
    ax.bar(
        param_names,
        param_values,
        color=[provider_colors.get(name, "#143F74") for name in param_names],
    )
    for index, value in enumerate(param_values):
        ax.text(index, value + 3, f"{value:.0f}%", ha="center", fontsize=9)
    ax.set_ylim(0, 110)
    ax.set_ylabel("参数清晰度通过率（%）")
    ax.set_title(f"{guide_label}：单 canonical tool 参数清晰度观察")
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    path = args.output_dir / "chart-ai-difficulty.png"
    fig.savefig(path, dpi=150)
    plt.close(fig)
    chart_paths.append(path.name)

    # 3. error-recovery pass rate
    recovery_pass: dict[str, float] = {}
    if released:
        for supplier in suppliers:
            record = released_by_path.get(
                (supplier["provider_id"], supplier["access_path_id"]), {}
            )
            observation = record.get("error_recovery")
            if observation and "passed" in observation:
                recovery_pass[supplier["name"]] = (
                    observation["passed"] / observation["total"]
                )
    else:
        for supplier in suppliers:
            questions = supplier.get("recovery_questions") or []
            records = [
                record for record in recovery if record["question_id"] in questions
            ]
            if records:
                recovery_pass[supplier["name"]] = sum(
                    1 for record in records if record["passed"]
                ) / len(records)
    fig, ax = plt.subplots(figsize=(8, 5))
    bar_names = [
        supplier["name"] for supplier in suppliers if supplier["name"] in recovery_pass
    ]
    values = [recovery_pass[name] * 100 for name in bar_names]
    ax.bar(
        bar_names,
        values,
        color=[provider_colors.get(name, "#143F74") for name in bar_names],
    )
    ax.set_ylim(0, 105)
    ax.set_ylabel("失败自愈率（%，2 轮）")
    ax.set_title(f"{guide_label}：同一 canonical tool 的错误恢复观察")
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
    ax.imshow(
        matrix,
        cmap=ListedColormap(["#F3F7FA", "#2F78AD"]),
        aspect="auto",
    )
    ax.set_xticks(range(len(market_universe)))
    ax.set_xticklabels(market_universe, fontsize=9)
    ax.set_yticks(range(len(suppliers)))
    ax.set_yticklabels(
        [supplier.get("chart_label", supplier["name"]) for supplier in suppliers],
        fontsize=9,
    )
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
    ax.set_title(f"{guide_label}：发布事实中的货币覆盖")
    fig.tight_layout()
    path = args.output_dir / "chart-market-coverage.png"
    fig.savefig(path, dpi=150)
    plt.close(fig)
    chart_paths.append(path.name)

    input_digests = (
        {"released-observations": _digest(args.released)}
        if args.released
        else {
            "cap-direct-test": _digest(args.direct),
            "agent-param-fill": _digest(args.param),
            "agent-response-interpretation": _digest(args.interpret),
            "agent-error-recovery": _digest(args.recovery),
        }
    )
    manifest: dict[str, object] = {
        "charts": {path: _digest(args.output_dir / path) for path in chart_paths},
        "input_digests": input_digests,
        "rendered_at": edition_date,
    }
    (args.output_dir / "charts-manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    print(json.dumps(manifest, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
