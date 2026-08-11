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
_STATUS_STYLE = {
    "observed": ("●", "#12B76A"),
    "absent": ("—", "#94A3B8"),
    "blocked": ("△", "#F79009"),
    "unmeasured": ("◇", "#2F78AD"),
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
        evidence_path = evidence_dir / f'{released["evidence_id"]}-terminal.json'
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
        returned_symbols = {
            item.get("facts", {}).get("symbol") for item in positive
        }
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


def _render_evidence_matrix_svg(
    *,
    title: str,
    columns: list[tuple[str, str]],
    rows: list[dict[str, object]],
    row_key: str,
) -> str:
    parts = [
        (
            '<svg xmlns="http://www.w3.org/2000/svg" width="760" height="900" '
            'viewBox="0 0 760 900" role="img" aria-labelledby="title desc">'
        ),
        f"<title id=\"title\">{title}</title>",
        (
            '<desc id="desc">六条 Provider 与 Access Path 的固定样本公开证据状态；'
            "不代表全市场能力。</desc>"
        ),
        (
            '<defs><linearGradient id="header" x1="0" y1="0" x2="1" y2="0">'
            '<stop offset="0" stop-color="#143F74"/>'
            '<stop offset="0.58" stop-color="#2F78AD"/>'
            '<stop offset="1" stop-color="#6EB0C2"/></linearGradient><style>'
            'text{font-family:"Segoe UI","Microsoft YaHei","PingFang SC",'
            '"Noto Sans SC",sans-serif}'
            ".title{fill:#fff;font-size:34px;font-weight:800}"
            ".subtitle{fill:#E2E8F0;font-size:24px}"
            ".provider{fill:#0F172A;font-size:23px;font-weight:800}"
            ".meta{fill:#475569;font-size:19px}"
            ".head{fill:#143F74;font-size:23px;font-weight:800}"
            ".symbol{font-size:34px;font-weight:800}"
            ".legend{fill:#334155;font-size:22px}"
            "</style></defs>"
        ),
        (
            '<rect width="760" height="900" fill="#F8FAFC"/>'
            '<rect width="760" height="155" fill="url(#header)"/>'
        ),
        f'<text x="38" y="58" class="title">{title}</text>',
        (
            '<text x="38" y="103" class="subtitle">'
            "6 条 Provider × Access Path · 每条适用路径 3 轮</text>"
        ),
        '<text x="38" y="138" class="subtitle">固定样本证据 · 不代表全市场能力</text>',
        (
            '<text x="38" y="190" class="legend">'
            '<tspan fill="#12B76A" font-weight="800">●</tspan> 已观察　'
            '<tspan fill="#F79009" font-weight="800">△</tspan> 阻断</text>'
        ),
        (
            '<text x="38" y="225" class="legend">'
            '<tspan fill="#94A3B8" font-weight="800">—</tspan> 未观察/未发布　'
            '<tspan fill="#2F78AD" font-weight="800">◇</tspan> 未独立测量</text>'
        ),
        (
            '<rect x="24" y="250" width="712" height="568" rx="16" '
            'fill="#FFFFFF" stroke="#E2E8F0"/>'
            '<rect x="24" y="250" width="712" height="88" rx="16" '
            'fill="#F1F5F9"/>'
        ),
        (
            '<text x="132" y="287" text-anchor="middle" class="head">'
            'Provider</text><text x="132" y="317" text-anchor="middle" '
            'class="head">Access Path · 样本</text>'
        ),
    ]
    for center, (first, second) in zip((305, 425, 545, 665), columns, strict=True):
        parts.append(
            f'<text x="{center}" y="287" text-anchor="middle" class="head">'
            f'{first}</text><text x="{center}" y="317" text-anchor="middle" '
            f'class="head">{second}</text>'
        )
    parts.append(
        '<g stroke="#E2E8F0"><path '
        'd="M240 250 V818 M365 250 V818 M485 250 V818 M605 250 V818"/>'
        '<path d="M24 338 H736 M24 418 H736 M24 498 H736 M24 578 H736 '
        'M24 658 H736 M24 738 H736"/></g>'
    )
    for index, row in enumerate(rows):
        top = 338 + index * 80
        parts.append(
            f'<text x="38" y="{top + 31}" class="provider">'
            f'{row["provider"]}</text><text x="38" y="{top + 61}" '
            f'class="meta">{row["meta"]}</text>'
        )
        for center, status in zip((305, 425, 545, 665), row[row_key], strict=True):
            symbol, color = _STATUS_STYLE[status]
            parts.append(
                f'<text x="{center}" y="{top + 52}" text-anchor="middle" '
                f'class="symbol" fill="{color}">{symbol}</text>'
            )
    parts.append(
        '<text x="380" y="864" text-anchor="middle" class="legend">'
        "灰色不是能力否定；橙色记录不可直接采信</text></svg>\n"
    )
    return "".join(parts)


def render_dividend_evidence_matrices(
    release_dir: Path,
    evidence_dir: Path,
    output_dir: Path,
    *,
    edition_date: str,
) -> dict[str, object]:
    release_path = release_dir / "release.json"
    rows = _dividend_evidence_rows(release_path, evidence_dir)
    charts = {
        "dividend-core-evidence.svg": _render_evidence_matrix_svg(
            title="Dividend Event 核心可用性证据",
            columns=[
                ("单次金额", "语义"),
                ("除权除息", "日期"),
                ("无效", "symbol"),
                ("证券身份", "验证"),
            ],
            rows=rows,
            row_key="core",
        ),
        "dividend-field-evidence.svg": _render_evidence_matrix_svg(
            title="Dividend Event 响应字段证据",
            columns=[
                ("响应内", "币种"),
                ("公告", "日期"),
                ("登记", "日期"),
                ("支付", "日期"),
            ],
            rows=rows,
            row_key="fields",
        ),
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    for name, content in charts.items():
        (output_dir / name).write_text(content, encoding="utf-8")
    manifest: dict[str, object] = {
        "release_id": json.loads(release_path.read_text(encoding="utf-8"))[
            "release"
        ]["release_id"],
        "charts": {
            name: _sha256_identity(output_dir / name) for name in sorted(charts)
        },
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
    parser.add_argument("--cases", type=Path)
    parser.add_argument("--edition-date", default="2026-08-11")
    args = parser.parse_args(argv)

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
