from __future__ import annotations

import hashlib
import io
import json
import platform
import tempfile
from collections import Counter
from collections.abc import Iterator
from contextlib import contextmanager
from importlib.resources import files
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.patches import Patch, Rectangle
from PIL import Image

from qveris_bench.articles import factory as v1
from qveris_bench.models.selection import SelectionSnapshotRow

_FONT_ROOT = files("qveris_bench").joinpath("assets", "fonts")
_FONT_PATHS = (
    Path(str(_FONT_ROOT.joinpath("QVerisCharts-Regular.otf"))),
    Path(str(_FONT_ROOT.joinpath("QVerisCharts-Bold.otf"))),
)
for _font_path in _FONT_PATHS:
    font_manager.fontManager.addfont(_font_path)
_FONT_FAMILY = font_manager.FontProperties(fname=_FONT_PATHS[0]).get_name()


@contextmanager
def _render_context() -> Iterator[None]:
    with plt.rc_context(
        {
            "font.family": "sans-serif",
            "font.sans-serif": [_FONT_FAMILY],
            "axes.unicode_minus": False,
        }
    ):
        yield


def build_article_package(
    selection_snapshot_path: Path,
    profile_path: Path,
    output_dir: Path,
    *,
    writer_input_path: Path | None = None,
    editorial_path: Path | None = None,
) -> v1.ArticleBuild:
    with _render_context():
        built = v1.build_article_package(
            selection_snapshot_path,
            profile_path,
            output_dir,
            writer_input_path=writer_input_path,
            editorial_path=editorial_path,
        )
        snapshot = v1._load_snapshot(selection_snapshot_path)
        profile = v1._load_profile(profile_path)
        rows = tuple(
            sorted(
                snapshot.rows,
                key=lambda row: (row.provider_name, row.access_path_id),
            )
        )
        display_names = {
            provider_id: links["name"]
            for provider_id, links in profile["provider_links"].items()
        }
        _render_runtime_chart(
            v1._runtime_rows(rows),
            display_names,
            profile["cap_label"],
            built.runtime_chart,
        )
        _render_market_chart(
            v1._market_rows(rows),
            display_names,
            profile["cap_label"],
            built.market_chart,
        )
    article = built.article.read_text(encoding="utf-8").replace(
        "A released successful sample returned ",
        "A released successful sample recorded ",
    )
    built.article.write_text(article, encoding="utf-8")
    manifest = json.loads(built.manifest.read_text(encoding="utf-8"))
    manifest["renderer_version"] = 2
    manifest["charts"] = {
        built.runtime_chart.name: _digest(built.runtime_chart.read_bytes()),
        built.market_chart.name: _digest(built.market_chart.read_bytes()),
    }
    built.manifest.write_bytes(v1._canonical_json(manifest))
    return built


def reproduce_article_package(
    selection_snapshot_path: Path,
    profile_path: Path,
    output_dir: Path,
    *,
    writer_input_path: Path | None = None,
    editorial_path: Path | None = None,
    expected_manifest_digest: str | None = None,
) -> None:
    manifest = output_dir / "manifest.json"
    if expected_manifest_digest is not None and _digest(
        manifest.read_bytes()
    ) != expected_manifest_digest:
        raise v1.ArticleBuildError(
            "article manifest digest does not match expected digest"
        )
    with tempfile.TemporaryDirectory(prefix="qveris-article-v2-") as temporary:
        rebuilt = build_article_package(
            selection_snapshot_path,
            profile_path,
            Path(temporary),
            writer_input_path=writer_input_path,
            editorial_path=editorial_path,
        )
        artifacts = (
            (output_dir / "article.md", rebuilt.article, "article"),
            (output_dir / "article-facts.json", rebuilt.article_facts, "article facts"),
            (output_dir / "manifest.json", rebuilt.manifest, "article manifest"),
            (
                output_dir / "charts/latency-list-price-tradeoff.png",
                rebuilt.runtime_chart,
                "runtime chart",
            ),
            (
                output_dir / "charts/market-coverage.png",
                rebuilt.market_chart,
                "market chart",
            ),
        )
        for committed, fresh, name in artifacts:
            if committed.read_bytes() == fresh.read_bytes():
                continue
            if (
                name.endswith("chart")
                and platform.system() != "Linux"
                and _same_pixels(committed, fresh)
            ):
                continue
            raise v1.ArticleBuildError(f"{name} artifact differs from a fresh build")


def _render_runtime_chart(
    rows: tuple[SelectionSnapshotRow, ...],
    display_names: dict[str, str],
    cap_label: str,
    path: Path,
) -> None:
    fig, axis = plt.subplots(figsize=(11, 6.5), facecolor="#F8FAFC")
    axis.set_facecolor("#F8FAFC")
    palette = ("#143F74", "#2F78AD", "#6EB0C2", "#FF8C00", "#334155")
    for index, row in enumerate(rows):
        metrics = row.gateway_metrics
        price = row.qveris_list_price
        assert metrics.latency_median_ms is not None
        assert metrics.latency_min_ms is not None
        assert metrics.latency_max_ms is not None
        assert price.amount_credits is not None
        axis.errorbar(
            metrics.latency_median_ms,
            price.amount_credits,
            xerr=[
                [metrics.latency_median_ms - metrics.latency_min_ms],
                [metrics.latency_max_ms - metrics.latency_median_ms],
            ],
            fmt="o",
            color=palette[index % len(palette)],
            markersize=9,
            capsize=4,
        )
        axis.annotate(
            display_names[row.provider_id],
            (metrics.latency_median_ms, price.amount_credits),
            xytext=(7, 7),
            textcoords="offset points",
            fontsize=9,
        )
    axis.set_xlabel("Median QVeris gateway latency (ms; bar = min-max)")
    axis.set_ylabel("QVeris list price (credits/call)")
    axis.set_title(f"{cap_label}: latency vs QVeris list price")
    axis.grid(True, color="#E2E8F0")
    fig.subplots_adjust(left=0.11, right=0.98, top=0.89, bottom=0.13)
    _save_png(fig, path)


def _render_market_chart(
    rows: tuple[SelectionSnapshotRow, ...],
    display_names: dict[str, str],
    cap_label: str,
    path: Path,
) -> None:
    markets = tuple(item.market for item in rows[0].market_coverage.results)  # type: ignore[union-attr]
    fig, axis = plt.subplots(figsize=(11.5, 6.2), facecolor="#F8FAFC")
    axis.set_facecolor("#F8FAFC")
    colors = {
        "verified": "#12B76A",
        "provider_negative": "#F04438",
        "evidence_insufficient": "#FF8C00",
        "not_applicable": "#E2E8F0",
    }
    for row_index, row in enumerate(rows):
        results = {item.market: item for item in row.market_coverage.results}  # type: ignore[union-attr]
        for column_index, market in enumerate(markets):
            result = results[market]
            axis.add_patch(
                Rectangle(
                    (column_index - 0.5, row_index - 0.5),
                    1,
                    1,
                    facecolor=colors[result.state],
                    edgecolor="white",
                )
            )
            label = (
                "N/A"
                if result.state == "not_applicable"
                else f"{result.passed_rounds}/{result.total_rounds}"
            )
            axis.text(
                column_index,
                row_index,
                label,
                ha="center",
                va="center",
                color=(
                    "white"
                    if result.state in {"verified", "provider_negative"}
                    else "#0F172A"
                ),
                fontsize=9,
                fontweight="bold",
            )
    axis.set_xlim(-0.5, len(markets) - 0.5)
    axis.set_ylim(len(rows) - 0.5, -0.5)
    axis.set_xticks(range(len(markets)), markets)
    axis.set_yticks(range(len(rows)), _market_chart_labels(rows, display_names))
    axis.tick_params(length=0)
    axis.set_title(f"{cap_label}: representative-market evidence", fontsize=16)
    axis.legend(
        handles=[
            Patch(color=value, label=v1._market_state_label(key))
            for key, value in colors.items()
        ],
        loc="upper center",
        bbox_to_anchor=(0.5, -0.15),
        ncol=2,
    )
    fig.subplots_adjust(left=0.35, right=0.98, top=0.88, bottom=0.28)
    _save_png(fig, path)


def _market_chart_labels(
    rows: tuple[SelectionSnapshotRow, ...], display_names: dict[str, str]
) -> list[str]:
    names = [display_names[row.provider_id] for row in rows]
    counts = Counter(names)
    return [
        name
        if counts[name] == 1
        else f"{name} ({row.access_path_id})"
        for row, name in zip(rows, names, strict=True)
    ]


def _save_png(fig: Any, path: Path) -> None:
    rendered = io.BytesIO()
    fig.savefig(rendered, format="png", dpi=180, metadata={})
    plt.close(fig)
    rendered.seek(0)
    with Image.open(rendered) as image:
        image.convert("RGBA").save(
            path,
            format="PNG",
            compress_level=9,
            optimize=False,
        )


def _same_pixels(first: Path, second: Path) -> bool:
    with Image.open(first) as expected, Image.open(second) as actual:
        expected_rgba = expected.convert("RGBA")
        actual_rgba = actual.convert("RGBA")
        return (
            expected_rgba.size == actual_rgba.size
            and expected_rgba.tobytes() == actual_rgba.tobytes()
        )


def _digest(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()
