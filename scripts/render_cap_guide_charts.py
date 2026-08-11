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
from matplotlib.patches import Patch

try:
    from chart_metrics import direct_metrics_by_access_path
except ModuleNotFoundError:
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


def _sha256_identity(path: Path) -> str:
    return f"sha256:{hashlib.sha256(path.read_bytes()).hexdigest()}"


_DIVIDEND_PROVIDERS = {
    "hangseng": "恒生聚源",
    "ifind": "同花顺 iFinD",
    "twelve-data": "Twelve Data",
    "alpha-vantage": "Alpha Vantage",
    "eodhd": "EODHD",
    "massive-stocks": "Massive",
}


def _directory_digest(path: Path) -> str:
    digest = hashlib.sha256()
    for item in sorted(path.glob("*.json")):
        digest.update(item.name.encode())
        digest.update(b"\0")
        digest.update(item.read_bytes())
    return f"sha256:{digest.hexdigest()}"


def _field_status(
    records: list[dict[str, object]],
    field: str,
    *,
    identity_blocked: bool,
    completed: bool,
) -> str:
    present = all(item.get("facts", {}).get(field) is not None for item in records)
    if not present:
        return "absent"
    if identity_blocked or not completed:
        return "blocked"
    return "observed"


def _dividend_evidence_rows(
    release_path: Path,
    evidence_dir: Path,
) -> list[dict[str, object]]:
    document = json.loads(release_path.read_text(encoding="utf-8"))
    released_by_run_key = {item["run_key"]: item for item in document["evidence"]}
    terminals: dict[str, dict[str, object]] = {}
    for run_key, released in released_by_run_key.items():
        evidence_path = evidence_dir / f"{released['evidence_id']}-terminal.json"
        if _sha256_identity(evidence_path) != released["public_digest"]:
            raise ValueError(f"public evidence digest mismatch: {evidence_path.name}")
        terminals[run_key] = json.loads(evidence_path.read_text(encoding="utf-8"))

    applicable = [
        cell
        for cell in document["cells"]
        if cell["applicable"] and cell["mode"] == "direct"
    ]
    rows: list[dict[str, object]] = []
    for provider_id, provider_label in _DIVIDEND_PROVIDERS.items():
        positive_cells = [
            cell
            for cell in applicable
            if cell["provider_id"] == provider_id
            and cell["case_id"] != "invalid-dividend-symbol"
        ]
        negative_cells = [
            cell
            for cell in applicable
            if cell["provider_id"] == provider_id
            and cell["case_id"] == "invalid-dividend-symbol"
        ]
        if len(positive_cells) != 3 or len(negative_cells) != 3:
            raise ValueError(
                f"expected three positive and negative rounds: {provider_id}"
            )
        positive = [terminals[cell["run_key"]] for cell in positive_cells]
        negative = [terminals[cell["run_key"]] for cell in negative_cells]
        requested_symbol = positive_cells[0]["case_input"]["symbol"]
        returned_symbols = {item.get("facts", {}).get("symbol") for item in positive}
        identity_blocked = any(
            symbol is not None and symbol != requested_symbol
            for symbol in returned_symbols
        )
        completed = all(item["state"] == "completed" for item in positive)

        transport = positive[0]["transport"]
        access_path_label = "Native MCP" if transport == "native_mcp" else "QVeris"
        market = "A 股" if positive_cells[0]["case_id"].startswith("cn-") else "美股"
        rows.append(
            {
                "provider": provider_label,
                "meta": f"{access_path_label} · {market} · {requested_symbol}",
                "core": [
                    _field_status(
                        positive,
                        "amount",
                        identity_blocked=identity_blocked,
                        completed=completed,
                    ),
                    _field_status(
                        positive,
                        "effective_date",
                        identity_blocked=identity_blocked,
                        completed=completed,
                    ),
                    (
                        "observed"
                        if all(item["state"] == "completed" for item in negative)
                        else "blocked"
                    ),
                    "blocked" if identity_blocked else "unmeasured",
                ],
                "fields": [
                    _field_status(
                        positive,
                        field,
                        identity_blocked=identity_blocked,
                        completed=completed,
                    )
                    for field in (
                        "currency",
                        "declaration_date",
                        "record_date",
                        "payment_date",
                    )
                ],
            }
        )
    return rows


def render_dividend_evidence_heatmap(
    release_dir: Path,
    evidence_dir: Path,
    output_dir: Path,
    *,
    edition_date: str,
) -> dict[str, object]:
    release_path = release_dir / "release.json"
    rows = _dividend_evidence_rows(release_path, evidence_dir)
    columns = [
        "单次金额\n语义",
        "除权除息日",
        "无效 symbol\n处理",
        "证券身份\n一致性",
        "响应内\n币种",
        "公告日",
        "登记日",
        "支付日",
    ]
    status_values = {"absent": 0, "unmeasured": 1, "blocked": 2, "observed": 3}
    status_text = {
        "absent": "未观察",
        "unmeasured": "未独立\n测量",
        "blocked": "阻断",
        "observed": "3/3",
    }
    matrix_statuses = [row["core"] + row["fields"] for row in rows]
    matrix = [
        [status_values[status] for status in row_statuses]
        for row_statuses in matrix_statuses
    ]

    output_dir.mkdir(parents=True, exist_ok=True)
    chart_name = "dividend-evidence-heatmap.png"
    chart_path = output_dir / chart_name
    colors = ["#F1F5F9", "#DCEAF2", "#F79009", "#12B76A"]
    fig, ax = plt.subplots(figsize=(14, 7.6), facecolor="#FFFFFF")
    ax.set_facecolor("#FFFFFF")
    ax.imshow(matrix, cmap=ListedColormap(colors), vmin=0, vmax=3, aspect="auto")
    ax.set_xticks(range(len(columns)))
    ax.set_xticklabels(columns, fontsize=12, color="#334155")
    ax.set_yticks(range(len(rows)))
    ax.set_yticklabels(
        [f"{row['provider']}\n{row['meta']}" for row in rows],
        fontsize=11,
        color="#334155",
    )
    for row_index, row_statuses in enumerate(matrix_statuses):
        for column_index, status in enumerate(row_statuses):
            label = status_text[status]
            if status == "blocked" and rows[row_index]["provider"] == "恒生聚源":
                label = "身份\n阻断"
            ax.text(
                column_index,
                row_index,
                label,
                ha="center",
                va="center",
                fontsize=11,
                fontweight="bold",
                color="#0F172A",
            )
    ax.axvline(3.5, color="#FFFFFF", linewidth=5)
    ax.text(
        0.25,
        1.035,
        "核心可用性",
        transform=ax.transAxes,
        ha="center",
        color="#143F74",
        fontsize=13,
        fontweight="bold",
    )
    ax.text(
        0.75,
        1.035,
        "响应字段丰富度",
        transform=ax.transAxes,
        ha="center",
        color="#143F74",
        fontsize=13,
        fontweight="bold",
    )
    ax.set_title(
        "6 条 Access Path 的 Dividend Event 证据并不相同",
        color="#143F74",
        fontsize=20,
        fontweight="bold",
        pad=52,
    )
    for spine in ax.spines.values():
        spine.set_color("#E2E8F0")
    ax.tick_params(length=0)
    ax.set_xticks([index - 0.5 for index in range(1, len(columns))], minor=True)
    ax.set_yticks([index - 0.5 for index in range(1, len(rows))], minor=True)
    ax.grid(which="minor", color="#FFFFFF", linewidth=3)
    ax.tick_params(which="minor", bottom=False, left=False)
    legend = [
        Patch(facecolor="#12B76A", label="3 轮均观察到"),
        Patch(facecolor="#F79009", label="语义或身份阻断"),
        Patch(facecolor="#DCEAF2", label="未独立测量"),
        Patch(facecolor="#F1F5F9", edgecolor="#E2E8F0", label="未观察 / 未发布"),
    ]
    ax.legend(
        handles=legend,
        loc="upper center",
        bbox_to_anchor=(0.5, -0.17),
        ncol=4,
        frameon=False,
        fontsize=11,
    )
    footer = f"数据来源：QVeris Research，{edition_date}；灰色不代表供应商没有该能力"
    fig.text(
        0.08,
        0.025,
        footer,
        color="#475569",
        fontsize=10.5,
    )
    fig.subplots_adjust(left=0.22, right=0.98, top=0.78, bottom=0.24)
    fig.savefig(chart_path, dpi=180, facecolor=fig.get_facecolor())
    plt.close(fig)

    chart_data = {
        "scope": "固定样本证据，不代表全市场能力",
        "footer": footer,
        "columns": columns,
        "rows": rows,
    }
    manifest: dict[str, object] = {
        "release_id": json.loads(release_path.read_text(encoding="utf-8"))["release"][
            "release_id"
        ],
        "charts": {chart_name: _sha256_identity(chart_path)},
        "data": chart_data,
        "input_digests": {
            "release": _sha256_identity(release_path),
            "public_evidence": _directory_digest(evidence_dir),
        },
        "rendered_at": edition_date,
    }
    (output_dir / "evidence-matrix-manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest


def render_selection_tradeoff(
    selection_snapshot_path: Path,
    output_dir: Path,
) -> dict[str, object]:
    snapshot = json.loads(selection_snapshot_path.read_text(encoding="utf-8"))
    rows = []
    for item in snapshot["rows"]:
        metrics = item["gateway_metrics"]
        if metrics["state"] != "measured":
            continue
        rows.append(
            {
                "provider": (
                    "Massive"
                    if item["provider_id"] == "massive-stocks"
                    else item["provider_name"]
                ),
                "access_path": "QVeris",
                "median_latency_ms": metrics["latency_median_ms"],
                "min_latency_ms": metrics["latency_min_ms"],
                "max_latency_ms": metrics["latency_max_ms"],
                "median_credits": metrics["median_credits"],
                "latency_samples": metrics["latency_sample_size"],
                "cost_samples": metrics["cost_sample_size"],
            }
        )
    rows.sort(key=lambda item: item["median_latency_ms"])
    sample_sizes = {(item["latency_samples"], item["cost_samples"]) for item in rows}
    if len(sample_sizes) != 1:
        raise ValueError("selection chart requires consistent sample sizes")
    latency_samples, cost_samples = next(iter(sample_sizes))

    output_dir.mkdir(parents=True, exist_ok=True)
    chart_name = "dividend-runtime-tradeoff.png"
    chart_path = output_dir / chart_name
    colors = ["#2F78AD", "#6EB0C2", "#143F74", "#FF8C00", "#12B76A"]
    fig, ax = plt.subplots(figsize=(11, 6.5), facecolor="#F8FAFC")
    ax.set_facecolor("#F8FAFC")
    for index, item in enumerate(rows):
        median_latency = item["median_latency_ms"]
        min_latency = item["min_latency_ms"]
        max_latency = item["max_latency_ms"]
        credits = item["median_credits"]
        ax.errorbar(
            median_latency,
            credits,
            xerr=[
                [median_latency - min_latency],
                [max_latency - median_latency],
            ],
            fmt="o",
            markersize=11,
            capsize=5,
            color=colors[index % len(colors)],
            ecolor="#94A3B8",
            elinewidth=2,
            zorder=3,
        )
        ax.annotate(
            item["provider"],
            (median_latency, credits),
            textcoords="offset points",
            xytext=(9, 10 if index % 2 == 0 else -18),
            fontsize=11,
            fontweight=600,
            color="#0F172A",
        )
    ax.set_xlabel("QVeris gateway 延迟中位数（ms；横线为最小—最大）", color="#334155")
    ax.set_ylabel("成功调用 credits 中位数", color="#334155")
    ax.set_title(
        "一次 Dividend Event 调用：延迟与 credits 的取舍",
        color="#143F74",
        fontsize=18,
        fontweight=600,
        pad=18,
    )
    ax.grid(True, color="#E2E8F0", linewidth=1)
    for spine in ax.spines.values():
        spine.set_color("#CBD5E1")
    edition = snapshot["edition"]
    fig.text(
        0.09,
        0.025,
        f"QVeris gateway 小样本观测 · {edition} · 每条路径 latency "
        f"n={latency_samples}，credits n={cost_samples}；"
        "不是 Native API SLA 或官网价格",
        color="#475569",
        fontsize=9.5,
    )
    fig.subplots_adjust(left=0.1, right=0.96, top=0.84, bottom=0.17)
    fig.savefig(chart_path, dpi=180, facecolor=fig.get_facecolor())
    plt.close(fig)

    manifest: dict[str, object] = {
        "snapshot_id": snapshot["snapshot_id"],
        "charts": {chart_name: _sha256_identity(chart_path)},
        "data": {"rows": rows},
        "input_digests": {
            "selection_snapshot": _sha256_identity(selection_snapshot_path),
        },
        "rendered_at": edition,
    }
    (output_dir / "selection-charts-manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest


def render_release_outcomes(
    release_dir: Path,
    cases_path: Path,
    output_dir: Path,
    *,
    edition_date: str,
) -> dict[str, object]:
    release_path = release_dir / "release.json"
    document = json.loads(release_path.read_text(encoding="utf-8"))
    applicable = [cell for cell in document["cells"] if cell["applicable"]]
    case_document = yaml.safe_load(cases_path.read_text(encoding="utf-8"))
    case_roles = {
        case["case_id"]: case["negative_control"] for case in case_document["cases"]
    }
    unknown_case_ids = {
        cell["case_id"] for cell in applicable if cell["case_id"] not in case_roles
    }
    if unknown_case_ids:
        joined = ", ".join(sorted(unknown_case_ids))
        raise ValueError(f"release contains cases absent from CAP Pack: {joined}")
    provider_labels = {
        "hangseng": "恒生聚源\nQVeris",
        "ifind": "同花顺 iFinD\nNative MCP",
        "twelve-data": "Twelve Data\nQVeris",
        "alpha-vantage": "Alpha Vantage\nQVeris",
        "eodhd": "EODHD\nQVeris",
        "massive-stocks": "Massive\nQVeris",
    }
    provider_order = [
        provider_id
        for provider_id in provider_labels
        if any(cell["provider_id"] == provider_id for cell in applicable)
    ]
    results = {
        provider_id: {
            "positive_completed": 0,
            "positive_total": 0,
            "negative_completed": 0,
            "negative_total": 0,
        }
        for provider_id in provider_order
    }
    for cell in applicable:
        result = results[cell["provider_id"]]
        kind = "negative" if case_roles[cell["case_id"]] else "positive"
        result[f"{kind}_total"] += 1
        if cell["state"] == "completed":
            result[f"{kind}_completed"] += 1

    output_dir.mkdir(parents=True, exist_ok=True)
    positions = list(range(len(provider_order)))
    width = 0.36
    positive = [
        results[provider_id]["positive_completed"] for provider_id in provider_order
    ]
    negative = [
        results[provider_id]["negative_completed"] for provider_id in provider_order
    ]
    positive_total = [
        results[provider_id]["positive_total"] for provider_id in provider_order
    ]
    negative_total = [
        results[provider_id]["negative_total"] for provider_id in provider_order
    ]

    fig, ax = plt.subplots(figsize=(10, 5.8), facecolor="#F8FAFC")
    ax.set_facecolor("#F8FAFC")
    positive_bars = ax.bar(
        [position - width / 2 for position in positions],
        positive,
        width,
        label="正向用例完成轮次",
        color="#2F78AD",
    )
    negative_bars = ax.bar(
        [position + width / 2 for position in positions],
        negative,
        width,
        label="负向控制完成轮次",
        color="#6EB0C2",
    )
    for bars, values, totals in (
        (positive_bars, positive, positive_total),
        (negative_bars, negative, negative_total),
    ):
        for bar, value, total in zip(bars, values, totals, strict=True):
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                value + 0.08,
                f"{value}/{total}",
                ha="center",
                color="#0F172A",
                fontsize=9,
            )
    ax.set_xticks(positions)
    ax.set_xticklabels([provider_labels[item] for item in provider_order], fontsize=9)
    ax.set_ylim(0, 3.65)
    ax.set_ylabel("完成轮次（每项分母为 3）", color="#0F172A")
    ax.set_title(
        "分红事件 Direct Test：正向字段门槛与负向控制",
        color="#143F74",
        fontsize=14,
        fontweight="bold",
    )
    ax.grid(axis="y", alpha=0.2, color="#94A3B8")
    ax.legend(frameon=False, loc="upper center", ncol=2)
    for spine in ax.spines.values():
        spine.set_color("#CBD5E1")
    fig.tight_layout()
    chart_path = output_dir / "chart-direct-outcomes.png"
    fig.savefig(chart_path, dpi=180, facecolor=fig.get_facecolor())
    plt.close(fig)

    manifest: dict[str, object] = {
        "release_id": document["release"]["release_id"],
        "charts": {chart_path.name: _sha256_identity(chart_path)},
        "input_digests": {
            "release": _sha256_identity(release_path),
            "cases": _sha256_identity(cases_path),
        },
        "rendered_at": edition_date,
    }
    (output_dir / "charts-manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest


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
    parser.add_argument("--release-dir", type=Path)
    parser.add_argument("--selection-snapshot", type=Path)
    parser.add_argument("--cases", type=Path)
    parser.add_argument("--edition-date", default="2026-08-11")
    args = parser.parse_args(argv)

    if args.selection_snapshot:
        manifest = render_selection_tradeoff(
            args.selection_snapshot,
            args.output_dir,
        )
        print(json.dumps(manifest, ensure_ascii=False))
        return 0

    if args.release_dir:
        if not args.cases:
            parser.error("--cases is required with --release-dir")
        manifest = render_release_outcomes(
            args.release_dir,
            args.cases,
            args.output_dir,
            edition_date=args.edition_date,
        )
        print(json.dumps(manifest, ensure_ascii=False))
        return 0

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

    latency: dict[tuple[str, str], float] = {}
    cost: dict[tuple[str, str], float] = {}
    labels = {
        (supplier["provider_id"], supplier["access_path_id"]): supplier.get(
            "chart_label", supplier["name"]
        )
        for supplier in suppliers
    }
    path_metrics = direct_metrics_by_access_path(direct, suppliers)
    for supplier in suppliers:
        key = (supplier["provider_id"], supplier["access_path_id"])
        metrics = path_metrics[key]
        if metrics["latency_ms"] is not None:
            latency[key] = metrics["latency_ms"]
        if metrics["cost_credits"] is not None:
            cost[key] = metrics["cost_credits"]

    def _question_ids(supplier: dict[str, object]) -> list[str]:
        questions = supplier.get("param_questions") or []
        if questions:
            return list(questions)
        legacy = supplier.get("param_question")
        return [legacy] if legacy else []

    parameter_clarity: dict[tuple[str, str], tuple[int, int]] = {}
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
                key = (supplier["provider_id"], supplier["access_path_id"])
                parameter_clarity[key] = (
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
                key = (supplier["provider_id"], supplier["access_path_id"])
                parameter_clarity[key] = (
                    sum(1 for record in records if record["passed"]),
                    len(records),
                )

    args.output_dir.mkdir(parents=True, exist_ok=True)
    chart_paths: list[str] = []

    # 1. latency vs cost scatter
    path_keys = [key for key in latency if key in cost]
    provider_colors = {
        "Alpha Vantage": "#143F74",
        "Twelve Data": "#2F78AD",
        "EODHD": "#6EB0C2",
        "融聚汇": "#8E6BBE",
    }
    fig, ax = plt.subplots(figsize=(8, 5))
    for key in path_keys:
        name = labels[key]
        ax.scatter(
            latency[key],
            cost[key],
            s=140,
            color=provider_colors.get(name, "#143F74"),
            zorder=3,
        )
        ax.annotate(
            name,
            (latency[key], cost[key]),
            textcoords="offset points",
            xytext=(8, 8),
            fontsize=9,
        )
    if not path_keys:
        ax.text(0.5, 0.5, "暂无符合 release 规范的观测", ha="center", va="center")
    ax.set_xlabel(f"实测平均延迟（ms，{observation_date}）")
    ax.set_ylabel("实测单次费用（QVeris credits）")
    ax.set_title(f"{guide_label}：QVeris Access Path 延迟与观测费用")
    ax.grid(True, alpha=0.3)
    fig.subplots_adjust(left=0.12, right=0.97, bottom=0.15, top=0.88)
    path = args.output_dir / "chart-latency-cost.png"
    fig.savefig(path, dpi=150)
    plt.close(fig)
    chart_paths.append(path.name)

    # 2. parameter clarity
    fig, ax = plt.subplots(figsize=(9, 5))
    param_keys = [
        (supplier["provider_id"], supplier["access_path_id"])
        for supplier in suppliers
        if (supplier["provider_id"], supplier["access_path_id"]) in parameter_clarity
    ]
    param_names = [labels[key] for key in param_keys]
    param_values = [
        parameter_clarity[key][0] / parameter_clarity[key][1] * 100
        for key in param_keys
    ]
    ax.bar(
        param_names,
        param_values,
        color=[provider_colors.get(name, "#143F74") for name in param_names],
    )
    for index, value in enumerate(param_values):
        ax.text(index, value + 3, f"{value:.0f}%", ha="center", fontsize=9)
    if not param_keys:
        ax.text(0.5, 0.5, "暂无符合 release 规范的观测", ha="center", va="center")
    ax.set_ylim(0, 110)
    ax.set_ylabel("参数清晰度通过率（%）")
    ax.set_title(f"{guide_label}：单 canonical tool 参数清晰度观察")
    ax.grid(True, alpha=0.3)
    fig.subplots_adjust(left=0.12, right=0.97, bottom=0.15, top=0.88)
    path = args.output_dir / "chart-ai-difficulty.png"
    fig.savefig(path, dpi=150)
    plt.close(fig)
    chart_paths.append(path.name)

    # 3. error-recovery pass rate
    recovery_pass: dict[tuple[str, str], float] = {}
    if released:
        for supplier in suppliers:
            record = released_by_path.get(
                (supplier["provider_id"], supplier["access_path_id"]), {}
            )
            observation = record.get("error_recovery")
            if observation and "passed" in observation:
                key = (supplier["provider_id"], supplier["access_path_id"])
                recovery_pass[key] = observation["passed"] / observation["total"]
    else:
        for supplier in suppliers:
            questions = supplier.get("recovery_questions") or []
            records = [
                record for record in recovery if record["question_id"] in questions
            ]
            if records:
                key = (supplier["provider_id"], supplier["access_path_id"])
                recovery_pass[key] = sum(
                    1 for record in records if record["passed"]
                ) / len(records)
    fig, ax = plt.subplots(figsize=(8, 5))
    recovery_keys = [
        (supplier["provider_id"], supplier["access_path_id"])
        for supplier in suppliers
        if (supplier["provider_id"], supplier["access_path_id"]) in recovery_pass
    ]
    bar_names = [labels[key] for key in recovery_keys]
    values = [recovery_pass[key] * 100 for key in recovery_keys]
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
    if not recovery_keys:
        ax.text(0.5, 0.5, "暂无符合 release 规范的观测", ha="center", va="center")
    fig.subplots_adjust(left=0.12, right=0.97, bottom=0.15, top=0.88)
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
    ax.set_title(f"{guide_label}：历史公开观测与工具契约中的货币覆盖")
    fig.tight_layout()
    path = args.output_dir / "chart-market-coverage.png"
    fig.savefig(path, dpi=150)
    plt.close(fig)
    chart_paths.append(path.name)

    input_digests = (
        {
            "chart-data": _digest(args.data),
            "released-observations": _digest(args.released),
        }
        if args.released
        else {
            "chart-data": _digest(args.data),
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
