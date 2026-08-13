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
from matplotlib.patches import Patch, Rectangle

_FONT_ROOT = files("qveris_bench").joinpath("assets", "fonts")
_FONT_PATHS = (
    Path(str(_FONT_ROOT.joinpath("QVerisCharts-Regular.otf"))),
    Path(str(_FONT_ROOT.joinpath("QVerisCharts-Bold.otf"))),
)
for _font_path in _FONT_PATHS:
    font_manager.fontManager.addfont(_font_path)
_CHART_FONT_FAMILY = font_manager.FontProperties(fname=_FONT_PATHS[0]).get_name()
plt.rcParams["font.family"] = ["sans-serif"]
plt.rcParams["font.sans-serif"] = [_CHART_FONT_FAMILY]
plt.rcParams["axes.unicode_minus"] = False

_DIVIDEND_PROVIDERS = {
    "hangseng": "Hang Seng",
    "ifind": "iFinD",
    "alpha-vantage": "Alpha Vantage",
    "twelve-data": "Twelve Data",
    "eodhd": "EODHD",
    "massive-stocks": "Massive",
}


def _sha256_identity(path: Path) -> str:
    return f"sha256:{hashlib.sha256(path.read_bytes()).hexdigest()}"


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
        list_price = item["qveris_list_price"]
        if list_price["state"] != "declared":
            raise ValueError("QVeris runtime chart requires inspect list pricing")
        rows.append(
            {
                "provider": _DIVIDEND_PROVIDERS[item["provider_id"]],
                "access_path": "QVeris",
                "median_latency_ms": metrics["latency_median_ms"],
                "min_latency_ms": metrics["latency_min_ms"],
                "max_latency_ms": metrics["latency_max_ms"],
                "list_price_credits": list_price["amount_credits"],
                "price_inspected_at": list_price["inspected_at"],
                "latency_samples": metrics["latency_sample_size"],
            }
        )
    rows.sort(key=lambda item: item["median_latency_ms"])
    sample_sizes = {item["latency_samples"] for item in rows}
    if len(sample_sizes) != 1:
        raise ValueError("selection chart requires consistent sample sizes")
    latency_samples = next(iter(sample_sizes))
    inspection_dates = {item["price_inspected_at"] for item in rows}
    if len(inspection_dates) != 1:
        raise ValueError("selection chart requires one inspect pricing snapshot")
    inspection_date = next(iter(inspection_dates))

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
        credits = item["list_price_credits"]
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
            fontweight=700,
            color="#0F172A",
        )
    ax.set_xlabel(
        "Median QVeris gateway latency (ms; bar shows min-max)",
        color="#334155",
    )
    ax.set_ylabel("QVeris list price (credits/call)", color="#334155")
    ax.set_title(
        "Dividend Event: latency vs QVeris list price",
        color="#143F74",
        fontsize=18,
        fontweight=700,
        pad=18,
    )
    ax.grid(True, color="#E2E8F0", linewidth=1)
    for spine in ax.spines.values():
        spine.set_color("#CBD5E1")
    edition = snapshot["edition"]
    fig.text(
        0.09,
        0.025,
        f"QVeris gateway sample · {edition} · n={latency_samples} per path; "
        f"list credits from qveris inspect ({inspection_date}), not account billing",
        color="#475569",
        fontsize=9.5,
    )
    fig.subplots_adjust(left=0.1, right=0.96, top=0.84, bottom=0.17)
    fig.savefig(chart_path, dpi=180, facecolor=fig.get_facecolor())
    plt.close(fig)

    provider_order = {
        provider_id: index for index, provider_id in enumerate(_DIVIDEND_PROVIDERS)
    }
    snapshot_rows = sorted(
        snapshot["rows"],
        key=lambda item: (
            provider_order.get(item["provider_id"], len(provider_order)),
            item["provider_id"],
            item["access_path_id"],
        ),
    )
    market_rows = []
    for item in snapshot_rows:
        provider_id = item["provider_id"]
        coverage = item["market_coverage"]
        access_path_label = (
            "Native MCP" if item["access_path_type"] == "native_mcp" else "QVeris"
        )
        market_rows.append(
            {
                "provider_id": provider_id,
                "access_path_id": item["access_path_id"],
                "provider": _DIVIDEND_PROVIDERS[provider_id],
                "access_path_type": item["access_path_type"],
                "access_path": access_path_label,
                "label": (
                    f"{_DIVIDEND_PROVIDERS[provider_id]} · {access_path_label} · "
                    f"{item['access_path_id']}"
                ),
                "results": {result["market"]: result for result in coverage["results"]},
            }
        )
    markets = ["US", "HK", "CN", "JP", "DE", "FR", "BR", "IN", "ES"]
    if any(set(item["results"]) != set(markets) for item in market_rows):
        raise ValueError("selection market chart requires the frozen market set")
    observation_dates = {
        item["market_coverage"]["observation_date"] for item in snapshot_rows
    }
    release_digests = {
        item["market_coverage"]["release_digest"] for item in snapshot_rows
    }
    if len(observation_dates) != 1 or len(release_digests) != 1:
        raise ValueError("selection market chart requires one market release")
    observation_date = next(iter(observation_dates))
    market_release_digest = next(iter(release_digests))
    selection_digest = _sha256_identity(selection_snapshot_path)
    total_rounds = {
        result["total_rounds"]
        for item in market_rows
        for result in item["results"].values()
    }
    if len(total_rounds) != 1:
        raise ValueError("selection market chart requires one round count")
    round_count = next(iter(total_rounds))
    market_title = (
        "Dividend Event results: "
        f"{len(markets)} representative markets × {len(market_rows)} Access Paths"
    )
    market_data = {
        "title": market_title,
        "edition": snapshot["edition"],
        "observation_date": observation_date,
        "release_digest": market_release_digest,
        "markets": markets,
        "rows": market_rows,
    }
    market_chart_name = "dividend-market-coverage.png"
    market_chart_path = output_dir / market_chart_name
    fig, ax = plt.subplots(figsize=(14, 7.4), facecolor="#FFFFFF")
    state_colors = {
        "verified": "#12B76A",
        "provider_negative": "#F79009",
        "not_applicable": "#E5EEF5",
    }
    for row_index, item in enumerate(market_rows):
        for column_index, market in enumerate(markets):
            state = item["results"][market]["state"]
            result = item["results"][market]
            label = (
                "N/A"
                if state == "not_applicable"
                else f"{result['passed_rounds']}/{result['total_rounds']}"
            )
            ax.add_patch(
                Rectangle(
                    (column_index - 0.5, row_index - 0.5),
                    1,
                    1,
                    facecolor=state_colors[state],
                    edgecolor="#FFFFFF",
                    linewidth=1.4,
                )
            )
            ax.text(
                column_index,
                row_index,
                label,
                ha="center",
                va="center",
                color="#FFFFFF" if state != "not_applicable" else "#475569",
                fontsize=11,
                fontweight=700,
            )
    ax.set_xlim(-0.5, len(markets) - 0.5)
    ax.set_ylim(len(market_rows) - 0.5, -0.5)
    ax.set_xticks(range(len(markets)))
    ax.set_xticklabels(markets, fontsize=11, color="#334155")
    ax.set_yticks(range(len(market_rows)))
    ax.set_yticklabels(
        [item["label"].replace(" · ", "\n", 1) for item in market_rows],
        fontsize=10,
        color="#334155",
    )
    ax.tick_params(length=0)
    for spine in ax.spines.values():
        spine.set_visible(False)
    fig.suptitle(
        market_title,
        color="#143F74",
        fontsize=20,
        fontweight=700,
        y=0.96,
    )
    fig.legend(
        handles=[
            Patch(
                facecolor="#12B76A",
                label=f"{round_count}/{round_count} sample passed",
            ),
            Patch(
                facecolor="#F79009",
                label=f"0/{round_count} sample did not pass",
            ),
            Patch(
                facecolor="#E5EEF5",
                edgecolor="#CBD5E1",
                label="N/A · explicitly not applicable",
            ),
        ],
        loc="lower center",
        ncol=3,
        frameon=False,
        bbox_to_anchor=(0.5, 0.055),
        fontsize=10,
    )
    fig.text(
        0.08,
        0.018,
        f"Market Release {observation_date} · "
        f"{round_count} rounds per applicable cell · "
        f"{market_release_digest[:23]}… · Selection {selection_digest[:23]}… · "
        "one representative symbol per market; not full-market coverage",
        color="#475569",
        fontsize=9.5,
    )
    fig.subplots_adjust(left=0.2, right=0.97, top=0.86, bottom=0.17)
    fig.savefig(market_chart_path, dpi=180, facecolor=fig.get_facecolor())
    plt.close(fig)

    manifest: dict[str, object] = {
        "snapshot_id": snapshot["snapshot_id"],
        "charts": {
            chart_name: _sha256_identity(chart_path),
            market_chart_name: _sha256_identity(market_chart_path),
        },
        "data": {"rows": rows, "market_coverage": market_data},
        "input_digests": {
            "selection_snapshot": selection_digest,
        },
        "renderer": {
            "backend": "Agg",
            "dpi": 180,
            "font_digests": [_sha256_identity(path) for path in _FONT_PATHS],
            "matplotlib": matplotlib.__version__,
            "numpy": version("numpy"),
            "pillow": version("pillow"),
        },
        "rendered_at": edition,
    }
    (output_dir / "selection-charts-manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest
