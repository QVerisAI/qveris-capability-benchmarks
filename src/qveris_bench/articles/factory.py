# ruff: noqa: E501

from __future__ import annotations

import hashlib
import json
import platform
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch, Rectangle
from PIL import Image, ImageChops
from pydantic import ValidationError

from qveris_bench.models.selection import SelectionSnapshot, SelectionSnapshotRow
from qveris_bench.yaml_io import YamlDocumentError, load_yaml_mapping


class ArticleBuildError(ValueError):
    pass


@dataclass(frozen=True)
class ArticleBuild:
    article: Path
    article_facts: Path
    runtime_chart: Path
    market_chart: Path
    manifest: Path


def reproduce_article_package(
    selection_snapshot_path: Path,
    profile_path: Path,
    output_dir: Path,
    *,
    expected_manifest_digest: str | None = None,
) -> None:
    manifest_path = output_dir / "manifest.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ArticleBuildError(f"invalid article manifest: {exc}") from exc
    if (
        expected_manifest_digest is not None
        and _digest(manifest_path.read_bytes()) != expected_manifest_digest
    ):
        raise ArticleBuildError(
            "article manifest digest does not match expected digest"
        )
    expected_inputs = {
        "selection_snapshot": _digest(selection_snapshot_path.read_bytes()),
        "profile": _digest(profile_path.read_bytes()),
    }
    if (
        not isinstance(manifest, dict)
        or manifest.get("input_digests", {}).get("selection_snapshot")
        != expected_inputs["selection_snapshot"]
        or manifest.get("input_digests", {}).get("profile")
        != expected_inputs["profile"]
    ):
        raise ArticleBuildError("article manifest input digest differs")
    with tempfile.TemporaryDirectory(prefix="qveris-article-") as temporary:
        rebuilt = build_article_package(
            selection_snapshot_path,
            profile_path,
            Path(temporary),
        )
        artifacts = (
            (output_dir / "article.md", rebuilt.article, "article"),
            (output_dir / "article-facts.json", rebuilt.article_facts, "article facts"),
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
            if not committed.is_file():
                raise ArticleBuildError(f"{name} artifact differs from a fresh build")
            if committed.read_bytes() == fresh.read_bytes():
                continue
            if (
                name.endswith("chart")
                and platform.system() != "Linux"
                and _same_pixels(committed, fresh)
            ):
                continue
            raise ArticleBuildError(f"{name} artifact differs from a fresh build")


def build_article_package(
    selection_snapshot_path: Path,
    profile_path: Path,
    output_dir: Path,
) -> ArticleBuild:
    snapshot = _load_snapshot(selection_snapshot_path)
    profile = _load_profile(profile_path)
    rows = tuple(
        sorted(snapshot.rows, key=lambda row: (row.provider_name, row.access_path_id))
    )
    _validate_publishable_rows(rows, profile)
    output_dir.mkdir(parents=True, exist_ok=True)
    chart_dir = output_dir / "charts"
    chart_dir.mkdir(exist_ok=True)
    facts = _article_facts(snapshot, rows, profile)
    article = output_dir / "article.md"
    facts_path = output_dir / "article-facts.json"
    runtime_chart = chart_dir / "latency-list-price-tradeoff.png"
    market_chart = chart_dir / "market-coverage.png"
    facts_path.write_bytes(_canonical_json(facts))
    display_names = {
        provider_id: links["name"]
        for provider_id, links in profile["provider_links"].items()
    }
    runtime_rows = _runtime_rows(rows)
    market_rows = _market_rows(rows)
    _render_runtime_chart(
        runtime_rows, display_names, profile["cap_label"], runtime_chart
    )
    _render_market_chart(market_rows, display_names, profile["cap_label"], market_chart)
    article.write_text(_render_article(facts, profile), encoding="utf-8")
    manifest = output_dir / "manifest.json"
    manifest.write_bytes(
        _canonical_json(
            {
                "schema_version": 1,
                "cap_id": snapshot.cap_id,
                "edition": snapshot.edition.isoformat(),
                "input_digests": {
                    "selection_snapshot": _digest(selection_snapshot_path.read_bytes()),
                    "profile": _digest(profile_path.read_bytes()),
                    "article_facts": _digest(facts_path.read_bytes()),
                },
                "outputs": {
                    "article": article.name,
                    "article_facts": facts_path.name,
                },
                "charts": {
                    runtime_chart.name: _digest(runtime_chart.read_bytes()),
                    market_chart.name: _digest(market_chart.read_bytes()),
                },
            }
        )
    )
    return ArticleBuild(article, facts_path, runtime_chart, market_chart, manifest)


def _load_snapshot(path: Path) -> SelectionSnapshot:
    try:
        return SelectionSnapshot.model_validate_json(path.read_bytes())
    except (OSError, ValidationError, ValueError) as exc:
        raise ArticleBuildError(f"invalid selection snapshot: {exc}") from exc


def _load_profile(path: Path) -> dict[str, Any]:
    try:
        profile = load_yaml_mapping(path)
    except (OSError, YamlDocumentError) as exc:
        raise ArticleBuildError(f"invalid article profile: {exc}") from exc
    required = ("title", "meta_description", "cap_label", "scope", "provider_links")
    if any(
        not isinstance(profile.get(key), str) or not profile[key]
        for key in required[:-1]
    ):
        raise ArticleBuildError("article profile is missing required English copy")
    if not isinstance(profile.get("provider_links"), dict):
        raise ArticleBuildError("article profile is missing provider links")
    allowed_links = profile.get("allowed_links")
    if (
        not isinstance(allowed_links, list)
        or not allowed_links
        or not all(
            isinstance(item, str) and item.startswith("https://")
            for item in allowed_links
        )
    ):
        raise ArticleBuildError("article profile is missing an HTTPS link allowlist")
    return profile


def _validate_publishable_rows(
    rows: tuple[SelectionSnapshotRow, ...], profile: dict[str, Any]
) -> None:
    if not rows:
        raise ArticleBuildError("selection snapshot has no Access Paths")
    expected_markets: set[str] | None = None
    for row in rows:
        links = profile["provider_links"].get(row.provider_id)
        if (
            not isinstance(links, dict)
            or not isinstance(links.get("official"), str)
            or not isinstance(links.get("name"), str)
        ):
            raise ArticleBuildError(
                f"article profile has no official link for {row.provider_id}"
            )
        if row.access_path_type.value == "qveris_connector" and not isinstance(
            links.get("qveris"), str
        ):
            raise ArticleBuildError(
                f"article profile has no QVeris link for {row.provider_id}"
            )
        for key in ("official", "qveris"):
            url = links.get(key)
            if url is not None and (
                not isinstance(url, str) or url not in profile["allowed_links"]
            ):
                raise ArticleBuildError("article profile contains an unapproved link")
        pricing = row.official_pricing
        if (
            pricing.state == "declared"
            and str(pricing.pricing_url) not in profile["allowed_links"]
        ):
            raise ArticleBuildError("article profile contains an unapproved link")
        if row.market_coverage is None:
            continue
        markets = {item.market for item in row.market_coverage.results}
        if expected_markets is None:
            expected_markets = markets
        elif markets != expected_markets:
            raise ArticleBuildError("market coverage must use one market universe")
    if not _runtime_rows(rows):
        raise ArticleBuildError(
            "runtime chart requires measured gateway and price facts"
        )
    if not _market_rows(rows):
        raise ArticleBuildError("market chart requires release-backed market coverage")
    for key in ("publication_manifest", "publication_attestation"):
        value = profile.get(key)
        if value is not None and (
            not isinstance(value, str)
            or not value
            or Path(value).is_absolute()
            or ".." in Path(value).parts
        ):
            raise ArticleBuildError("article profile has an invalid publication path")


def _article_facts(
    snapshot: SelectionSnapshot,
    rows: tuple[SelectionSnapshotRow, ...],
    profile: dict[str, Any],
) -> dict[str, Any]:
    coverage_rows = _market_rows(rows)
    first_coverage = coverage_rows[0].market_coverage
    if first_coverage is None:
        raise ArticleBuildError("market chart requires release-backed market coverage")
    all_markets = tuple(item.market for item in first_coverage.results)
    records: list[dict[str, Any]] = []
    for row in rows:
        coverage = row.market_coverage
        positive = [item for item in row.case_observations if not item.negative_control]
        negative = [item for item in row.case_observations if item.negative_control]
        records.append(
            {
                "provider_id": row.provider_id,
                "provider_name": profile["provider_links"][row.provider_id]["name"],
                "access_path_id": row.access_path_id,
                "access_path_type": row.access_path_type.value,
                "positive": [_observation(item.outcome) for item in positive],
                "negative": [_observation(item.outcome) for item in negative],
                "terminal_observations": row.run_observations.terminal_observations,
                "planned_observations": row.run_observations.planned_observations,
                "verified_markets": [
                    item.market
                    for item in (coverage.results if coverage is not None else ())
                    if item.state == "verified"
                ],
                "market_results": [
                    {
                        "market": item.market,
                        "state": item.state,
                        "passed": item.passed_rounds,
                        "total": item.total_rounds,
                    }
                    for item in (coverage.results if coverage is not None else ())
                ],
                "latency_median_ms": row.gateway_metrics.latency_median_ms,
                "latency_min_ms": row.gateway_metrics.latency_min_ms,
                "latency_max_ms": row.gateway_metrics.latency_max_ms,
                "latency_samples": row.gateway_metrics.latency_sample_size,
                "list_price_credits": row.qveris_list_price.amount_credits,
                "list_price_inspected_at": (
                    row.qveris_list_price.inspected_at.isoformat()
                    if row.qveris_list_price.inspected_at is not None
                    else None
                ),
                "official_pricing": row.official_pricing.model_dump(mode="json"),
                "invalid_input": _observation(
                    row.agent_interface.invalid_input_handling
                ),
            }
        )
    return {
        "cap_id": snapshot.cap_id,
        "edition": snapshot.edition.isoformat(),
        "cap_release_digest": snapshot.cap_release_digest,
        "market_release_digest": snapshot.market_coverage_release_digest,
        "scope": profile["scope"],
        "provider_count": len({record["provider_id"] for record in records}),
        "access_path_count": len(records),
        "planned_observations": sum(
            row.run_observations.planned_observations for row in rows
        ),
        "terminal_observations": sum(
            row.run_observations.terminal_observations for row in rows
        ),
        "market_terminal_observations": sum(
            (
                row.market_coverage.run_observations.terminal_observations
                if row.market_coverage is not None
                and row.market_coverage.run_observations is not None
                else len(
                    {
                        evidence_ref
                        for result in (
                            row.market_coverage.results
                            if row.market_coverage is not None
                            else ()
                        )
                        for evidence_ref in result.evidence_refs
                    }
                )
            )
            for row in rows
        ),
        "markets": all_markets,
        "rows": records,
    }


def _observation(observation: Any) -> dict[str, int | str]:
    if observation.state != "measured":
        return {"state": "evidence_insufficient"}
    return {
        "state": "measured",
        "passed": observation.passed,
        "total": observation.total,
    }


def _render_article(facts: dict[str, Any], profile: dict[str, Any]) -> str:
    rows = facts["rows"]
    runtime_rows = [
        row
        for row in rows
        if row["latency_median_ms"] is not None
        and row["list_price_credits"] is not None
    ]
    fastest = min(runtime_rows, key=lambda row: row["latency_median_ms"])
    cheapest = min(runtime_rows, key=lambda row: row["list_price_credits"])
    broadest_count = max(len(row["verified_markets"]) for row in rows)
    broadest = [row for row in rows if len(row["verified_markets"]) == broadest_count]
    live_calls = (
        facts["terminal_observations"] + facts["market_terminal_observations"]
    )
    comparison = "\n".join(_comparison_row(row, profile) for row in rows)
    market_rows = "\n".join(_market_row(row, facts["markets"]) for row in rows)
    agent_rows = "\n".join(_agent_row(row) for row in rows)
    return f"""# {profile["title"]}

> {profile["meta_description"]}

{facts["scope"]} This edition covers {facts["provider_count"]} Providers × {facts["access_path_count"]} Access Paths, {_count_word(len(facts["markets"]))} representative markets, and {live_calls} release-backed live calls. Every metric below is scoped to the tested Access Path, not the provider's entire native API surface.

## Quick recommendations

- **Lowest observed QVeris list price:** {cheapest["provider_name"]} · {_path_label(cheapest)} at {cheapest["list_price_credits"]:g} credits/call in this frozen inspect snapshot.
- **Lowest observed gateway latency:** {fastest["provider_name"]} · {_path_label(fastest)} at a {fastest["latency_median_ms"]:.0f} ms median across {fastest["latency_samples"]} samples.
{_market_recommendation(broadest, facts["markets"])}

These are separate trade-offs, not an overall winner.

## Comparison table

| Provider × Access Path | Fixed-sample outcome | Verified representative markets | Median gateway latency | QVeris list credits/call | Official provider pricing |
|---|---|---|---:|---:|---|
{comparison}

“Verified” means every frozen round met the CAP contract. “Provider-negative” means every round returned an explicit provider-level negative outcome; it does not prove permanent lack of support. “Not applicable” means the frozen plan explicitly excluded that market. “Evidence insufficient” means the Release did not establish a provider conclusion for that market.

## Market coverage

| Provider × Access Path | {" | ".join(facts["markets"])} |
|---|{"|".join("---" for _ in facts["markets"])}|
{market_rows}

The matrix is one representative symbol per market from the market Release; it is not a claim of full market coverage.

![Market coverage generated from the Selection Snapshot](charts/market-coverage.png)

## Latency and QVeris list-price trade-off

Latency is measured only through the QVeris gateway Access Path. Credits are QVeris inspect list prices, not an individual account's billed consumption or a provider's direct API plan.

![Latency and QVeris list-price trade-off generated from the Selection Snapshot](charts/latency-list-price-tradeoff.png)

## Agent integration notes

| Provider × Access Path | Invalid-input handling | Integration note |
|---|---:|---|
{agent_rows}

Do not treat this as an AI-friendly score. Validate the returned instrument identity, event date semantics, currency, pagination, and any market-specific symbol dialect in your own integration.

## How we tested, reproduce, and contribute

The baseline Release digest is `{facts["cap_release_digest"]}`. The market Release digest is `{facts["market_release_digest"]}`. Reproduce the package offline with `{_reproduce_command(profile)}`. To create a new edition, run the CAP with your own `QVERIS_API_KEY`; a rerun must use a new Release ID and never overwrite this evidence.

Suppliers may submit a binding, reproducible case, or factual correction through the repository. Inclusion and conclusions cannot be purchased.

## Limitations and FAQ

**Does this rank every provider?** No. It compares only the frozen Provider × Access Path cohort for this CAP edition.

**Does a verified market mean all symbols work?** No. It means the representative frozen market case satisfied the contract in every observed round.

**Why can a provider have different results elsewhere?** Native APIs, other connector tools, plan tiers, symbols, and observation dates are different access paths or test conditions.
"""


def _comparison_row(row: dict[str, Any], profile: dict[str, Any]) -> str:
    if not row["positive"] and not row["negative"]:
        outcome = (
            f"Terminal observations {row['terminal_observations']}/"
            f"{row['planned_observations']}"
        )
    else:
        positive = ", ".join(_fraction(item) for item in row["positive"])
        negative = ", ".join(_fraction(item) for item in row["negative"])
        outcome = f"Positive {positive}; invalid control {negative}"
    market = ", ".join(row["verified_markets"]) or "Evidence insufficient"
    links = profile["provider_links"][row["provider_id"]]
    cta = f" · [Try it in QVeris]({links['qveris']})" if "qveris" in links else ""
    return (
        f"| {row['provider_name']} · {_path_label(row)} · [Official site]({links['official']}){cta} "
        f"| {outcome} | {market} | {_runtime_value(row)} | {_price_value(row)} | {_official_price_value(row)} |"
    )


def _market_row(row: dict[str, Any], markets: tuple[str, ...]) -> str:
    results = {item["market"]: item for item in row["market_results"]}
    if not results:
        return (
            f"| {row['provider_name']} · {_path_label(row)} | "
            + " | ".join("Evidence insufficient" for _ in markets)
            + " |"
        )
    cells = []
    for market in markets:
        result = results[market]
        cells.append(
            "N/A"
            if result["state"] == "not_applicable"
            else f"{result['passed']}/{result['total']} {_market_state_label(result['state'])}"
        )
    return (
        f"| {row['provider_name']} · {_path_label(row)} | " + " | ".join(cells) + " |"
    )


def _agent_row(row: dict[str, Any]) -> str:
    invalid_input = _fraction(row["invalid_input"])
    note = (
        "Explicit rejection is release-backed."
        if row["invalid_input"].get("passed", 0) > 0
        else "No explicit rejection observed; handle failures defensively."
    )
    return f"| {row['provider_name']} · {_path_label(row)} | {invalid_input} | {note} |"


def _fraction(value: dict[str, Any]) -> str:
    return (
        "Evidence insufficient"
        if value["state"] != "measured"
        else f"{value['passed']}/{value['total']}"
    )


def _path_label(row: dict[str, Any]) -> str:
    return (
        "QVeris connector"
        if row["access_path_type"] == "qveris_connector"
        else "Native MCP"
    )


def _runtime_value(row: dict[str, Any]) -> str:
    if row["latency_median_ms"] is None:
        return "Evidence insufficient"
    return f"{row['latency_median_ms']:.0f} ms (n={row['latency_samples']})"


def _price_value(row: dict[str, Any]) -> str:
    if row["list_price_credits"] is None:
        return (
            "Not applicable"
            if row["access_path_type"] != "qveris_connector"
            else "Evidence insufficient"
        )
    return f"{row['list_price_credits']:g}"


def _official_price_value(row: dict[str, Any]) -> str:
    price = row["official_pricing"]
    if price["state"] != "declared":
        return "Evidence insufficient"
    return (
        f"{price['free_tier']}; {price['paid_plans']} "
        f"([official pricing]({price['pricing_url']}); verified {price['verified_at']})"
    )


def _market_recommendation(rows: list[dict[str, Any]], markets: tuple[str, ...]) -> str:
    if len(rows) == 1:
        row = rows[0]
        return (
            f"- **Broadest representative-market evidence:** {row['provider_name']} · "
            f"{_path_label(row)} verified {len(row['verified_markets'])} of "
            f"{len(markets)} tested markets."
        )
    names = ", ".join(row["provider_name"] for row in rows)
    return (
        f"- **Representative-market evidence:** {names} are tied at "
        f"{len(rows[0]['verified_markets'])} of {len(markets)} tested markets."
    )


def _reproduce_command(profile: dict[str, Any]) -> str:
    manifest = profile.get("publication_manifest")
    attestation = profile.get("publication_attestation")
    if not isinstance(manifest, str) or not isinstance(attestation, str):
        return (
            "qveris-bench publication reproduce --package <package-manifest> "
            "--expected-package-digest <published-digest>"
        )
    return (
        "qveris-bench publication reproduce --package "
        f"{manifest} --expected-package-digest \"$(uv run python -c "
        f"'import json; print(json.load(open(\"{attestation}\"))[\"package_digest\"])')\""
    )


def _count_word(value: int) -> str:
    words = {
        1: "one",
        2: "two",
        3: "three",
        4: "four",
        5: "five",
        6: "six",
        7: "seven",
        8: "eight",
        9: "nine",
        10: "ten",
    }
    return words.get(value, str(value))


def _market_state_label(state: str) -> str:
    return {
        "verified": "verified",
        "provider_negative": "provider-negative",
        "evidence_insufficient": "Evidence insufficient",
    }.get(state, state.replace("_", " "))


def _runtime_rows(
    rows: tuple[SelectionSnapshotRow, ...],
) -> tuple[SelectionSnapshotRow, ...]:
    return tuple(
        row
        for row in rows
        if row.gateway_metrics.state == "measured"
        and row.qveris_list_price.state == "declared"
    )


def _market_rows(
    rows: tuple[SelectionSnapshotRow, ...],
) -> tuple[SelectionSnapshotRow, ...]:
    return tuple(row for row in rows if row.market_coverage is not None)


def _render_runtime_chart(
    rows: tuple[SelectionSnapshotRow, ...],
    display_names: dict[str, str],
    cap_label: str,
    path: Path,
) -> None:
    fig, axis = plt.subplots(figsize=(10, 6), facecolor="#F8FAFC")
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
    axis.set_xlabel("Median QVeris gateway latency (ms; bar = min–max)")
    axis.set_ylabel("QVeris list price (credits/call)")
    axis.set_title(f"{cap_label}: latency vs QVeris list price")
    axis.grid(True, color="#E2E8F0")
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def _render_market_chart(
    rows: tuple[SelectionSnapshotRow, ...],
    display_names: dict[str, str],
    cap_label: str,
    path: Path,
) -> None:
    markets = tuple(item.market for item in rows[0].market_coverage.results)  # type: ignore[union-attr]
    fig, axis = plt.subplots(
        figsize=(max(7, len(markets) * 1.05), max(4.5, len(rows) * 0.7)),
        facecolor="#F8FAFC",
    )
    axis.set_facecolor("#F8FAFC")
    colors = {
        "verified": "#12B76A",
        "provider_negative": "#F04438",
        "evidence_insufficient": "#F79009",
        "not_applicable": "#E2E8F0",
    }
    for row_index, row in enumerate(rows):
        coverage = row.market_coverage
        assert coverage is not None
        results = {item.market: item for item in coverage.results}
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
    axis.set_yticks(
        range(len(rows)),
        [
            f"{display_names[row.provider_id]} · {_path_label(row.model_dump(mode='json'))}"
            for row in rows
        ],
    )
    axis.tick_params(length=0)
    axis.set_title(f"{cap_label}: representative-market evidence")
    axis.legend(
        handles=[
            Patch(color=value, label=_market_state_label(key))
            for key, value in colors.items()
        ],
        loc="upper center",
        bbox_to_anchor=(0.5, -0.13),
        ncol=3,
    )
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def _digest(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _same_pixels(first: Path, second: Path) -> bool:
    with Image.open(first) as expected, Image.open(second) as actual:
        expected_rgba = expected.convert("RGBA")
        actual_rgba = actual.convert("RGBA")
        return (
            expected_rgba.size == actual_rgba.size
            and ImageChops.difference(expected_rgba, actual_rgba).getbbox() is None
        )


def _canonical_json(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode()
