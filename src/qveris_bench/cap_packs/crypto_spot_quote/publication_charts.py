from __future__ import annotations

import hashlib
import json
from importlib.metadata import version
from importlib.resources import files
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.patches import Rectangle

_FONT_ROOT = files("qveris_bench").joinpath("assets", "fonts")
_FONT_PATHS = (
    Path(str(_FONT_ROOT.joinpath("QVerisCharts-Regular.otf"))),
    Path(str(_FONT_ROOT.joinpath("QVerisCharts-Bold.otf"))),
)
for _font_path in _FONT_PATHS:
    font_manager.fontManager.addfont(_font_path)
_FONT_FAMILY = font_manager.FontProperties(fname=_FONT_PATHS[0]).get_name()
plt.rcParams["font.family"] = ["sans-serif"]
plt.rcParams["font.sans-serif"] = [_FONT_FAMILY]
plt.rcParams["axes.unicode_minus"] = False


def _digest(path: Path) -> str:
    return f"sha256:{hashlib.sha256(path.read_bytes()).hexdigest()}"


def render_crypto_publication_charts(
    selection_snapshot_path: Path,
    output_dir: Path,
) -> dict[str, object]:
    snapshot = json.loads(selection_snapshot_path.read_text(encoding="utf-8"))
    rows = snapshot["rows"]
    if [row["provider_id"] for row in rows] != ["binance", "okx"]:
        raise ValueError("crypto charts require the frozen Provider order")
    output_dir.mkdir(parents=True, exist_ok=True)

    scope_data = [
        {
            "provider_id": row["provider_id"],
            "provider_name": row["provider_name"],
            "access_path_id": row["access_path_id"],
            "positive": row["positive"],
            "invalid_input": row["invalid_input"],
            "pair": row["asset_scope"]["pair"],
            "market": row["asset_scope"]["market"],
            "asset_type": row["asset_scope"]["asset_type"],
        }
        for row in rows
    ]
    _render_scope(scope_data, output_dir / "crypto-asset-scope.png")

    runtime_data = [
        {
            "provider_id": row["provider_id"],
            "provider_name": row["provider_name"],
            "access_path_id": row["access_path_id"],
            "latency_median_ms": row["gateway_metrics"]["latency_median_ms"],
            "latency_min_ms": row["gateway_metrics"]["latency_min_ms"],
            "latency_max_ms": row["gateway_metrics"]["latency_max_ms"],
            "latency_sample_size": row["gateway_metrics"]["latency_sample_size"],
            "amount_credits": row["qveris_list_price"]["amount_credits"],
            "inspected_at": row["qveris_list_price"]["inspected_at"],
        }
        for row in rows
    ]
    _render_runtime(runtime_data, output_dir / "crypto-latency-credits.png")

    chart_names = ("crypto-asset-scope.png", "crypto-latency-credits.png")
    return {
        "charts": {name: _digest(output_dir / name) for name in chart_names},
        "data": {
            "asset_scope": scope_data,
            "latency_and_list_price": runtime_data,
        },
        "input_digests": {"selection_snapshot": _digest(selection_snapshot_path)},
        "rendered_at": snapshot["edition"],
        "renderer": {
            "font_family": _FONT_FAMILY,
            "font_regular_digest": _digest(_FONT_PATHS[0]),
            "font_bold_digest": _digest(_FONT_PATHS[1]),
            "matplotlib": version("matplotlib"),
            "numpy": version("numpy"),
            "pillow": version("pillow"),
        },
    }


def _render_scope(rows: list[dict[str, object]], output: Path) -> None:
    fig, ax = plt.subplots(figsize=(11, 4.8), facecolor="#FFFFFF")
    columns = ("BTC/USDT required fields", "Invalid-pair control")
    for row_index, row in enumerate(rows):
        for column_index, key in enumerate(("positive", "invalid_input")):
            result = row[key]
            if not isinstance(result, dict):
                raise ValueError("crypto scope chart requires measured results")
            passed = result["passed"]
            total = result["total"]
            complete = passed == total == 3
            ax.add_patch(
                Rectangle(
                    (column_index - 0.5, row_index - 0.5),
                    1,
                    1,
                    facecolor="#12B76A" if complete else "#F79009",
                    edgecolor="#FFFFFF",
                    linewidth=2,
                )
            )
            ax.text(
                column_index,
                row_index,
                f"{passed}/{total}",
                ha="center",
                va="center",
                color="#FFFFFF",
                fontsize=14,
                fontweight=700,
            )
    ax.set_xlim(-0.5, len(columns) - 0.5)
    ax.set_ylim(len(rows) - 0.5, -0.5)
    ax.set_xticks(range(len(columns)), columns, fontsize=11, color="#334155")
    labels = [f"{row['provider_name']} · QVeris" for row in rows]
    ax.set_yticks(range(len(rows)), labels, fontsize=11, color="#0F172A")
    ax.tick_params(length=0)
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.set_title(
        "Tested asset scope: Global crypto spot · BTC/USDT only",
        color="#143F74",
        fontsize=17,
        fontweight=700,
        pad=20,
    )
    fig.text(
        0.12,
        0.035,
        "Each cell shows passed rounds / 3 fixed rounds; no other pair or "
        "native API was tested.",
        color="#475569",
        fontsize=9.5,
    )
    fig.subplots_adjust(left=0.25, right=0.96, top=0.78, bottom=0.2)
    fig.savefig(output, dpi=180, facecolor=fig.get_facecolor())
    plt.close(fig)


def _render_runtime(rows: list[dict[str, object]], output: Path) -> None:
    sample_sizes = {row["latency_sample_size"] for row in rows}
    inspection_dates = {row["inspected_at"] for row in rows}
    if sample_sizes != {3} or len(inspection_dates) != 1:
        raise ValueError("crypto runtime chart requires one complete pricing snapshot")
    inspected_at = next(iter(inspection_dates))

    fig, ax = plt.subplots(figsize=(11, 6.2), facecolor="#F8FAFC")
    ax.set_facecolor("#F8FAFC")
    colors = ("#2F78AD", "#FF8C00")
    offsets = ((10, 13), (10, -22))
    for index, row in enumerate(rows):
        median = _number(row, "latency_median_ms")
        minimum = _number(row, "latency_min_ms")
        maximum = _number(row, "latency_max_ms")
        credits = _number(row, "amount_credits")
        ax.errorbar(
            median,
            credits,
            xerr=[[median - minimum], [maximum - median]],
            fmt="o",
            markersize=12,
            capsize=5,
            color=colors[index],
            ecolor="#94A3B8",
            elinewidth=2,
            zorder=3,
        )
        ax.annotate(
            str(row["provider_name"]),
            (median, credits),
            textcoords="offset points",
            xytext=offsets[index],
            color="#0F172A",
            fontsize=12,
            fontweight=700,
        )
    ax.set_xlabel(
        "Median QVeris gateway latency (ms; line shows min-max)", color="#334155"
    )
    ax.set_ylabel("QVeris Inspect list price (credits/call)", color="#334155")
    ax.set_ylim(0.7, 1.3)
    ax.set_title(
        "Crypto Spot Quote: latency vs public QVeris list price",
        color="#143F74",
        fontsize=17,
        fontweight=700,
        pad=20,
    )
    ax.grid(True, color="#E2E8F0", linewidth=1)
    for spine in ax.spines.values():
        spine.set_color("#CBD5E1")
    fig.text(
        0.1,
        0.03,
        f"Positive BTC/USDT sample · n=3 per path · Inspect price observed "
        f"{inspected_at}; not account billing.",
        color="#475569",
        fontsize=9.5,
    )
    fig.subplots_adjust(left=0.1, right=0.96, top=0.82, bottom=0.18)
    fig.savefig(output, dpi=180, facecolor=fig.get_facecolor())
    plt.close(fig)


def _number(row: dict[str, object], key: str) -> float:
    value = row.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"crypto runtime chart requires numeric {key}")
    return float(value)
