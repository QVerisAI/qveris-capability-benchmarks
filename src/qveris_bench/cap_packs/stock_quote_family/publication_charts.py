from __future__ import annotations

import hashlib
import json
from importlib.resources import files
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.patches import Patch, Rectangle

_FONT_ROOT = files("qveris_bench").joinpath("assets", "fonts")
_REGULAR = Path(str(_FONT_ROOT.joinpath("QVerisCharts-Regular.otf")))
_BOLD = Path(str(_FONT_ROOT.joinpath("QVerisCharts-Bold.otf")))
for _path in (_REGULAR, _BOLD):
    font_manager.fontManager.addfont(_path)
_FONT_FAMILY = font_manager.FontProperties(fname=_REGULAR).get_name()
plt.rcParams["font.family"] = ["sans-serif"]
plt.rcParams["font.sans-serif"] = [_FONT_FAMILY]

_CASE_LABELS = {
    "aapl-quote": "AAPL quote",
    "aapl-freshness-precision": "Freshness",
    "cn-600519-market-coverage": "CN quote",
    "cn-600519-agent-contract": "Canonical\ncontract",
    "invalid-stock": "Invalid symbol",
}
_CASE_ORDER = tuple(_CASE_LABELS)


def render_stock_quote_outcomes(
    snapshot_path: Path, output_dir: Path
) -> dict[str, object]:
    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    rows = []
    for row in snapshot["rows"]:
        results = {result["case_id"]: result for result in row["case_results"]}
        if set(results) != set(_CASE_ORDER):
            raise ValueError("stock quote chart requires the frozen case set")
        rows.append(
            {
                "provider_id": row["provider_id"],
                "provider": row["provider_name"],
                "access_path_id": row["access_path_id"],
                "access_path": "QVeris",
                "qualified": row["qualified"],
                "results": {case_id: results[case_id] for case_id in _CASE_ORDER},
            }
        )
    if any(row["qualified"] for row in rows):
        raise ValueError("this edition is expected to have no qualified path")

    output_dir.mkdir(parents=True, exist_ok=True)
    chart_name = "stock-quote-outcomes.png"
    chart_path = output_dir / chart_name
    fig, ax = plt.subplots(figsize=(12.5, 5.4), facecolor="#FFFFFF")
    ax.set_xlim(0, len(_CASE_ORDER))
    ax.set_ylim(0, len(rows))
    ax.invert_yaxis()
    colors = {"passed": "#12B76A", "provider_negative": "#F79009"}
    for row_index, row in enumerate(rows):
        for column_index, case_id in enumerate(_CASE_ORDER):
            result = row["results"][case_id]
            ax.add_patch(
                Rectangle(
                    (column_index, row_index),
                    1,
                    1,
                    facecolor=colors[result["state"]],
                    edgecolor="#FFFFFF",
                    linewidth=3,
                )
            )
            ax.text(
                column_index + 0.5,
                row_index + 0.5,
                f"{result['passed_rounds']}/{result['total_rounds']}",
                ha="center",
                va="center",
                fontsize=15,
                fontweight=700,
                color="#0F172A",
            )
    ax.set_xticks(
        [index + 0.5 for index in range(len(_CASE_ORDER))],
        [_CASE_LABELS[case_id] for case_id in _CASE_ORDER],
        fontsize=11,
        color="#334155",
    )
    ax.set_yticks(
        [index + 0.5 for index in range(len(rows))],
        [f"{row['provider']} · QVeris\n{row['access_path_id']}" for row in rows],
        fontsize=11,
        color="#334155",
    )
    ax.tick_params(length=0)
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.set_title(
        "Stock Quote: no tested Access Path passed the positive scenarios",
        color="#143F74",
        fontsize=18,
        fontweight=700,
        pad=24,
    )
    fig.legend(
        handles=(
            Patch(facecolor="#12B76A", label="Passed every round"),
            Patch(facecolor="#F79009", label="Provider-negative every round"),
        ),
        loc="lower center",
        bbox_to_anchor=(0.5, 0.03),
        ncol=2,
        frameon=False,
        fontsize=10,
    )
    fig.text(
        0.5,
        0.01,
        f"Observed {snapshot['observation_date']} · "
        f"GitHub run {snapshot['github_run_id']} · "
        "fixed QVeris Access Paths · 3 rounds per case",
        ha="center",
        color="#475569",
        fontsize=9,
    )
    fig.subplots_adjust(left=0.25, right=0.97, top=0.79, bottom=0.24)
    fig.savefig(chart_path, dpi=180, facecolor=fig.get_facecolor())
    plt.close(fig)

    data = {
        "edition": snapshot["edition"],
        "observation_date": snapshot["observation_date"],
        "github_run_id": snapshot["github_run_id"],
        "cases": list(_CASE_ORDER),
        "rows": rows,
    }
    return {
        "rendered_at": snapshot["edition"],
        "input_digests": {
            "selection_snapshot": _digest(snapshot_path.read_bytes()),
            **snapshot["input_digests"],
        },
        "data": data,
        "charts": {chart_name: _digest(chart_path.read_bytes())},
    }


def _digest(content: bytes) -> str:
    return f"sha256:{hashlib.sha256(content).hexdigest()}"
