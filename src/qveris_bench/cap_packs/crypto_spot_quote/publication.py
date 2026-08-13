from __future__ import annotations

import hashlib
import json
import platform
import re
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from statistics import median
from typing import Any, cast

from PIL import Image, ImageChops

from qveris_bench.models.publication import PublicationPackageSpec
from qveris_bench.providers.repository import (
    ProviderRegistryEntry,
    ProviderRegistryRepository,
)
from qveris_bench.publications.service import (
    PublicationReproductionError,
    resolve_repository_path,
)
from qveris_bench.releases.canonical import release_digest
from qveris_bench.releases.replay import replay_release_dir
from qveris_bench.suites.compiler import compile_suite
from qveris_bench.suites.fingerprint import canonical_json_bytes
from qveris_bench.yaml_io import load_yaml_mapping

_POSITIVE_CASE = "crypto-btcusdt-spot-quote"
_NEGATIVE_CASE = "crypto-invalid-spot-symbol"
_PROVIDER_NAMES = {"binance": "Binance", "okx": "OKX"}


class CryptoSpotQuotePublicationAdapter:
    adapter_id = "crypto-spot-quote-v1"
    adapter_version = "1.0.0"
    cap_id = "crypto-spot-quote"

    def reproduce(
        self,
        *,
        repository_root: Path,
        package_path: Path,
        package: PublicationPackageSpec,
        document: Mapping[str, Any],
        output_dir: Path,
    ) -> tuple[str, ...]:
        del package_path
        if package.release_sections != ("release",):
            raise PublicationReproductionError(
                "Crypto Spot Quote publication requires exactly one Release"
            )
        artifacts = _mapping(document, "artifacts")
        selection_input = _artifact(
            repository_root, artifacts, "selection_snapshot_input"
        )
        committed_snapshot = _artifact(repository_root, artifacts, "selection_snapshot")
        fresh_snapshot = build_crypto_selection_snapshot(
            selection_input, repository_root
        )
        if fresh_snapshot != committed_snapshot.read_bytes():
            raise PublicationReproductionError(
                "selection snapshot differs from a fresh release-derived build"
            )
        snapshot = _json_mapping(committed_snapshot, "selection snapshot")
        if snapshot.get("cap_id") != package.cap_id:
            raise PublicationReproductionError(
                "publication package CAP does not match the Selection Snapshot"
            )
        _validate_manifest(document, artifacts, selection_input, committed_snapshot)

        generated = _render_charts(committed_snapshot, output_dir)
        _validate_charts(generated, artifacts, repository_root, output_dir)

        article_facts_path = _artifact(repository_root, artifacts, "article_facts")
        article_facts = _build_article_facts(snapshot, document, repository_root)
        expected_facts = canonical_json_bytes(article_facts)
        if article_facts_path.read_bytes() != expected_facts:
            raise PublicationReproductionError(
                "article facts differ from fresh release-derived facts"
            )
        if artifacts.get("article_facts_digest") != _digest(expected_facts):
            raise PublicationReproductionError("article facts digest mismatch")

        article_path = _artifact(repository_root, artifacts, "article")
        article = article_path.read_text(encoding="utf-8")
        profile = load_yaml_mapping(
            _artifact(repository_root, artifacts, "publication_profile")
        )
        _validate_article(article, article_facts, snapshot, document, profile)
        _validate_links(article, document)
        return ("selection_snapshot", "charts", "article_facts", "links")


def build_crypto_selection_snapshot(input_path: Path, root: Path) -> bytes:
    config = load_yaml_mapping(input_path)
    if config.get("cap_id") != "crypto-spot-quote":
        raise PublicationReproductionError("selection input CAP mismatch")
    edition = str(config.get("edition"))
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", edition):
        raise PublicationReproductionError("selection edition is invalid")
    cap_pack = resolve_repository_path(root, _string(config, "cap_pack"))
    providers_root = resolve_repository_path(root, _string(config, "providers_root"))
    harbor_contracts = resolve_repository_path(
        root, _string(config, "harbor_contracts")
    )
    release_spec = _mapping(config, "release")
    release_dir = resolve_repository_path(root, _string(release_spec, "directory"))
    release_path = release_dir / "release.json"
    release_bytes = release_path.read_bytes()
    expected_release_digest = _string(release_spec, "digest")
    if release_digest(release_bytes) != expected_release_digest:
        raise PublicationReproductionError("selection Release digest mismatch")
    replay_release_dir(release_dir, expected_digest=expected_release_digest)
    release = cast(dict[str, Any], json.loads(release_bytes))
    release_metadata = _mapping(release, "release")

    compiled = compile_suite(
        cap_pack / "suite.yaml",
        cap_pack / "cases.yaml",
        providers_root,
        cap_pack / "cap.yaml",
        harbor_contracts,
    )
    if compiled.suite.cap_id != config.get("cap_id"):
        raise PublicationReproductionError("selection suite contract drifted")
    frozen_plan = _json_mapping(release_dir / "run-plan.json", "frozen run plan")
    frozen_cells = _list_of_mappings(frozen_plan, "cells")
    current_cells = [cell.model_dump(mode="json") for cell in compiled.run_plan.cells]
    ignored = {"run_key", "suite_fingerprint", "state"}
    if (
        frozen_plan.get("suite_id") != compiled.suite.suite_id
        or frozen_plan.get("cap_id") != compiled.suite.cap_id
        or frozen_plan.get("cap_version") != str(compiled.suite.cap_version)
        or [
            {key: value for key, value in cell.items() if key not in ignored}
            for cell in frozen_cells
        ]
        != [
            {key: value for key, value in cell.items() if key not in ignored}
            for cell in current_cells
        ]
    ):
        raise PublicationReproductionError("selection run plan drifted")

    cells = _list_of_mappings(release, "cells")
    evidence = _list_of_mappings(release, "evidence")
    evidence_by_run = _unique_by(evidence, "run_key", "Release evidence")
    manifest = _json_mapping(
        release_dir / "public-evidence-manifest.json", "public evidence manifest"
    )
    manifest_entries = _list_of_mappings(manifest, "evidence")
    public_by_run = _unique_by(manifest_entries, "run_key", "public evidence")
    if set(evidence_by_run) != set(public_by_run):
        raise PublicationReproductionError(
            "public evidence run keys differ from Release evidence"
        )

    pricing_path = resolve_repository_path(root, _string(config, "qveris_list_pricing"))
    prices = _load_qveris_prices(pricing_path, edition)
    provider_order = config.get("provider_order")
    if provider_order != ["binance", "okx"]:
        raise PublicationReproductionError("selection Provider order drifted")
    qveris_provider_ids = _mapping(config, "qveris_provider_ids")
    qveris_provider_pages = _mapping(config, "qveris_provider_pages")
    symbol_dialects = _mapping(config, "symbol_dialects")
    records = {
        record.provider_id: record
        for record in ProviderRegistryRepository(providers_root).list()
    }

    rows: list[dict[str, object]] = []
    observed_dates: set[str] = set()
    for provider_id in provider_order:
        provider_cells = [
            cell for cell in cells if cell.get("provider_id") == provider_id
        ]
        identities = {str(cell.get("access_path_id")) for cell in provider_cells}
        if len(identities) != 1:
            raise PublicationReproductionError(
                "one Provider must retain one exact Crypto Access Path"
            )
        access_path_id = identities.pop()
        identity = (str(provider_id), access_path_id)
        record = records.get(str(provider_id))
        if record is None:
            raise PublicationReproductionError("selection Provider is not registered")
        access_paths = [
            path
            for path in record.access_paths
            if path.access_path_id == access_path_id
        ]
        if len(access_paths) != 1:
            raise PublicationReproductionError(
                "selection Provider and Access Path identity mismatch"
            )
        access_path = access_paths[0]
        price = prices.get(identity)
        if price is None or price["tool_id"] != access_path.canonical_interface:
            raise PublicationReproductionError("QVeris list price identity mismatch")
        if qveris_provider_ids.get(access_path_id) != price[
            "qveris_provider_id"
        ] or not str(qveris_provider_pages.get(access_path_id, "")).endswith(
            f"/{price['qveris_provider_id']}"
        ):
            raise PublicationReproductionError("QVeris Provider page identity mismatch")

        positive_cells = _case_cells(provider_cells, _POSITIVE_CASE)
        negative_cells = _case_cells(provider_cells, _NEGATIVE_CASE)
        if len(positive_cells) != 3 or len(negative_cells) != 3:
            raise PublicationReproductionError("Crypto case round count drifted")
        if any(cell.get("state") != "completed" for cell in positive_cells):
            raise PublicationReproductionError("Crypto positive outcome drifted")
        if any(
            cell.get("state") != "provider_negative"
            or cell.get("failure_attribution") != "provider_validation_error"
            for cell in negative_cells
        ):
            raise PublicationReproductionError("Crypto negative control drifted")

        scoped_cells = positive_cells + negative_cells
        scoped_evidence = [
            evidence_by_run[_string(cell, "run_key")] for cell in scoped_cells
        ]
        scoped_public = [
            public_by_run[_string(cell, "run_key")] for cell in scoped_cells
        ]
        refs = sorted(_string(item, "public_digest") for item in scoped_evidence)
        if refs != sorted(_string(item, "public_digest") for item in scoped_public):
            raise PublicationReproductionError("Crypto public evidence digest drifted")

        positive_terminals = [
            _terminal(root, public_by_run[_string(cell, "run_key")], cell)
            for cell in positive_cells
        ]
        negative_terminals = [
            _terminal(root, public_by_run[_string(cell, "run_key")], cell)
            for cell in negative_cells
        ]
        identity_label = "BTCUSDT"
        for terminal in positive_terminals:
            facts = _mapping(terminal, "facts")
            if facts.get("symbol") != identity_label or any(
                not isinstance(facts.get(field), (int, float))
                or isinstance(facts.get(field), bool)
                or float(cast(float, facts[field])) <= 0
                for field in ("price", "open", "high", "low")
            ):
                raise PublicationReproductionError("Crypto terminal facts drifted")
            timestamp = facts.get("timestamp")
            if not isinstance(timestamp, (int, float)):
                raise PublicationReproductionError("Crypto observation date is missing")
            observed_dates.add(
                datetime.fromtimestamp(timestamp / 1000, UTC).date().isoformat()
            )
        if any(_mapping(item, "facts") for item in negative_terminals):
            raise PublicationReproductionError(
                "Crypto negative control published quote facts"
            )

        latencies = sorted(
            float(evidence_by_run[_string(cell, "run_key")]["latency_ms"])
            for cell in positive_cells
        )
        pricing_fact = _official_pricing(record, access_path_id, edition)
        provider_path = providers_root / str(provider_id) / "provider.yaml"
        rows.append(
            {
                "access_path_id": access_path_id,
                "access_path_type": access_path.path_type.value,
                "agent_interface": {
                    "invalid_input_handling": {"passed": 3, "total": 3},
                    "pagination": {"state": "evidence_insufficient"},
                    "required_field_stability": {"passed": 3, "total": 3},
                    "returned_identity": {"passed": 3, "total": 3},
                    "single_tool_agent_trial": {"state": "not_applicable"},
                    "symbol_dialect": _string(symbol_dialects, access_path_id),
                },
                "asset_scope": {
                    "asset_type": "CRYPTO_SPOT",
                    "market": "GLOBAL",
                    "pair": "BTC/USDT",
                    "state": "verified_sample",
                },
                "evidence_ref_count": len(refs),
                "evidence_refs_digest": _digest(canonical_json_bytes(refs)),
                "gateway_metrics": {
                    "latency_evidence_refs": sorted(
                        _string(
                            evidence_by_run[_string(cell, "run_key")], "public_digest"
                        )
                        for cell in positive_cells
                    ),
                    "latency_max_ms": max(latencies),
                    "latency_median_ms": median(latencies),
                    "latency_min_ms": min(latencies),
                    "latency_sample_size": len(latencies),
                    "measurement_boundary": "qveris_gateway",
                },
                "invalid_input": {"passed": 3, "total": 3},
                "official_pricing": pricing_fact,
                "positive": {"passed": 3, "total": 3},
                "provider_id": str(provider_id),
                "provider_name": _PROVIDER_NAMES[str(provider_id)],
                "provider_registry_digest": _file_digest(provider_path),
                "qveris_list_price": {
                    **price,
                    "evidence_ref": _file_digest(pricing_path),
                    "inspected_at": edition,
                    "source": "qveris_inspect",
                    "unit": "per_call",
                },
                "qveris_provider_page": _string(qveris_provider_pages, access_path_id),
            }
        )

    if observed_dates != {edition}:
        raise PublicationReproductionError(
            "Crypto observation date does not match the publication edition"
        )
    if set(prices) != {
        (str(row["provider_id"]), str(row["access_path_id"])) for row in rows
    }:
        raise PublicationReproductionError(
            "QVeris list pricing identities differ from released identities"
        )
    cap_sources = release_metadata.get("cap_sources")
    if not isinstance(cap_sources, list) or len(cap_sources) != 1:
        raise PublicationReproductionError("Crypto Harbor source is invalid")
    input_digests = {
        name: _file_digest(cap_pack / filename)
        for name, filename in (
            ("cap", "cap.yaml"),
            ("cases", "cases.yaml"),
            ("observation_schema", "observation-schema.yaml"),
            ("outcome_rules", "outcome-rules.yaml"),
            ("provider_bindings", "provider-bindings.yaml"),
            ("suite", "suite.yaml"),
        )
    }
    input_digests.update(
        {
            "harbor_contracts": _file_digest(harbor_contracts),
            "qveris_list_pricing": _file_digest(pricing_path),
            "release": expected_release_digest,
            "selection_input": _file_digest(input_path),
        }
    )
    snapshot = {
        "cap_id": "crypto-spot-quote",
        "cap_source": cap_sources[0],
        "edition": edition,
        "input_digests": input_digests,
        "limitations": config.get("limitations", []),
        "observation_date": edition,
        "release_digest": expected_release_digest,
        "release_id": release_metadata.get("release_id"),
        "rows": rows,
        "schema_version": 1,
        "snapshot_id": config.get("snapshot_id"),
        "suite_fingerprint": release_metadata.get("suite_fingerprint"),
        "total_live_calls": len(cells),
        "version": config.get("version"),
    }
    return canonical_json_bytes(snapshot)


def _load_qveris_prices(
    path: Path, edition: str
) -> dict[tuple[str, str], dict[str, object]]:
    document = _json_mapping(path, "QVeris list pricing")
    if (
        document.get("source") != "qveris_inspect"
        or document.get("inspected_at") != edition
        or document.get("disclosure_level") != "sanitized_public"
        or document.get("license_status") != "cleared"
        or document.get("extractor_version") != "1.0.0"
    ):
        raise PublicationReproductionError("QVeris list pricing provenance mismatch")
    responses = _list_of_mappings(document, "responses")
    response_by_tool = _unique_by(responses, "tool_id", "Inspect responses")
    result: dict[tuple[str, str], dict[str, object]] = {}
    for item in _list_of_mappings(document, "prices"):
        identity = (_string(item, "provider_id"), _string(item, "access_path_id"))
        tool_id = _string(item, "tool_id")
        response = response_by_tool.get(tool_id)
        amount = item.get("amount_credits")
        if (
            identity in result
            or response is None
            or isinstance(amount, bool)
            or not isinstance(amount, (int, float))
            or amount < 0
            or response.get("amount_credits") != amount
            or response.get("provider_id") != item.get("qveris_provider_id")
            or response.get("billing_unit") != "call"
            or response.get("per") != 1
            or item.get("inspect_response_digest")
            != _digest(_compact_json_bytes(response))
        ):
            raise PublicationReproductionError("QVeris list pricing response mismatch")
        result[identity] = {
            "amount_credits": float(amount),
            "inspect_response_digest": item["inspect_response_digest"],
            "qveris_provider_id": item["qveris_provider_id"],
            "tool_id": tool_id,
        }
    if set(response_by_tool) != {str(item["tool_id"]) for item in result.values()}:
        raise PublicationReproductionError("QVeris Inspect response set differs")
    return result


def _terminal(
    root: Path, entry: Mapping[str, Any], cell: Mapping[str, Any]
) -> Mapping[str, Any]:
    terminal = _json_mapping(
        resolve_repository_path(root, _string(entry, "path")), "public terminal"
    )
    if (
        terminal.get("run_key") != cell.get("run_key")
        or terminal.get("case_id") != cell.get("case_id")
        or terminal.get("round") != cell.get("round")
        or terminal.get("state") != cell.get("state")
    ):
        raise PublicationReproductionError(
            "public terminal Provider, Access Path, or run identity drifted"
        )
    return terminal


def _official_pricing(
    record: ProviderRegistryEntry, access_path_id: str, edition: str
) -> dict[str, Any]:
    matches = [
        fact
        for fact in record.provider.official_pricing
        if fact.applies_to == "provider_wide" or access_path_id in fact.applies_to
    ]
    if len(matches) != 1:
        raise PublicationReproductionError("official pricing scope mismatch")
    fact = matches[0]
    if fact.verified_at.isoformat() > edition:
        raise PublicationReproductionError("official pricing is newer than edition")
    return fact.model_dump(mode="json")


def _build_article_facts(
    snapshot: Mapping[str, Any],
    manifest: Mapping[str, Any],
    root: Path,
) -> dict[str, object]:
    rows = _list_of_mappings(snapshot, "rows")
    release = _mapping(manifest, "release")
    release_path = resolve_repository_path(
        root, f"{_string(release, 'directory')}/release.json"
    )
    release_document = _json_mapping(release_path, "Release")
    cells = _list_of_mappings(release_document, "cells")
    fastest = min(
        rows,
        key=lambda row: float(_mapping(row, "gateway_metrics")["latency_median_ms"]),
    )
    return {
        "access_path_count": len(rows),
        "edition": snapshot["edition"],
        "package_id": _mapping(manifest, "publication_package")["package_id"],
        "provider_count": len({row["provider_id"] for row in rows}),
        "recommendations": {
            "fastest_observed_path": {
                "access_path_id": fastest["access_path_id"],
                "provider_name": fastest["provider_name"],
            },
            "same_qveris_list_price": len(
                {_mapping(row, "qveris_list_price")["amount_credits"] for row in rows}
            )
            == 1,
        },
        "release": {
            "applicable_cells": sum(bool(cell.get("applicable")) for cell in cells),
            "negative_control_cells": sum(
                cell.get("case_id") == _NEGATIVE_CASE for cell in cells
            ),
            "observation_date": snapshot["observation_date"],
            "planned_cells": len(cells),
            "positive_case_cells": sum(
                cell.get("case_id") == _POSITIVE_CASE for cell in cells
            ),
            "public_evidence_records": len(
                _list_of_mappings(release_document, "evidence")
            ),
            "release_digest": snapshot["release_digest"],
            "release_id": snapshot["release_id"],
            "rounds_per_cell": len({cell.get("round") for cell in cells}),
        },
        "rows": [
            {
                "access_path_id": row["access_path_id"],
                "access_path_type": row["access_path_type"],
                "evidence_ref_count": row["evidence_ref_count"],
                "evidence_refs_digest": row["evidence_refs_digest"],
                "invalid_input": row["invalid_input"],
                "latency_median_ms": _mapping(row, "gateway_metrics")[
                    "latency_median_ms"
                ],
                "official_pricing": row["official_pricing"],
                "positive": row["positive"],
                "provider_id": row["provider_id"],
                "provider_name": row["provider_name"],
                "qveris_list_price": row["qveris_list_price"],
                "qveris_provider_page": row["qveris_provider_page"],
                "symbol_dialect": _mapping(row, "agent_interface")["symbol_dialect"],
            }
            for row in rows
        ],
        "schema_version": 1,
        "total_live_calls": snapshot["total_live_calls"],
    }


def _validate_manifest(
    manifest: Mapping[str, Any],
    artifacts: Mapping[str, Any],
    selection_input: Path,
    snapshot_path: Path,
) -> None:
    snapshot = _json_mapping(snapshot_path, "selection snapshot")
    selection = _mapping(manifest, "selection_snapshot")
    if (
        str(manifest.get("edition")) != snapshot.get("edition")
        or selection.get("id") != snapshot.get("snapshot_id")
        or selection.get("input_digest") != _file_digest(selection_input)
        or selection.get("digest") != _file_digest(snapshot_path)
    ):
        raise PublicationReproductionError("selection manifest metadata drifted")
    release = _mapping(manifest, "release")
    facts = _mapping(snapshot, "cap_source")
    if (
        release.get("digest") != snapshot.get("release_digest")
        or release.get("suite_fingerprint") != snapshot.get("suite_fingerprint")
        or release.get("planned_cells") != 12
        or release.get("applicable_cells") != 12
        or release.get("public_evidence_records") != 12
        or release.get("rounds_per_cell") != 3
        or facts.get("harbor_capability_id") != "CRYPTO.SPOT.RT"
    ):
        raise PublicationReproductionError("publication Release metadata drifted")
    if not isinstance(artifacts.get("charts"), list) or len(artifacts["charts"]) != 2:
        raise PublicationReproductionError("publication chart set drifted")
    seo = _mapping(manifest, "seo")
    title = str(seo.get("title", ""))
    description = str(seo.get("meta_description", ""))
    if not 40 <= len(title) <= 60 or not 150 <= len(description) <= 160:
        raise PublicationReproductionError("publication SEO metadata drifted")


def _render_charts(snapshot: Path, output_dir: Path) -> dict[str, object]:
    from qveris_bench.cap_packs.crypto_spot_quote.publication_charts import (
        render_crypto_publication_charts,
    )

    return render_crypto_publication_charts(snapshot, output_dir / "charts")


def _validate_charts(
    generated: Mapping[str, Any],
    artifacts: Mapping[str, Any],
    root: Path,
    output_dir: Path,
) -> None:
    manifest_path = _artifact(root, artifacts, "selection_charts_manifest")
    if artifacts.get("selection_charts_manifest_digest") != _file_digest(manifest_path):
        raise PublicationReproductionError("selection chart manifest digest mismatch")
    committed = _json_mapping(manifest_path, "selection chart manifest")
    for field in ("data", "input_digests", "rendered_at", "renderer"):
        if committed.get(field) != generated.get(field):
            raise PublicationReproductionError(
                f"chart {field} differs from the committed chart manifest"
            )
    chart_values = artifacts.get("charts")
    if not isinstance(chart_values, list) or not all(
        isinstance(value, str) for value in chart_values
    ):
        raise PublicationReproductionError("publication charts must be declared")
    names = {Path(value).name for value in chart_values}
    committed_charts = _mapping(committed, "charts")
    generated_charts = _mapping(generated, "charts")
    if names != set(committed_charts) or names != set(generated_charts):
        raise PublicationReproductionError(
            "declared, committed, and generated chart sets must match"
        )
    for value in chart_values:
        path = resolve_repository_path(root, value)
        if committed_charts.get(path.name) != _file_digest(path):
            raise PublicationReproductionError(
                f"committed chart digest mismatch: {path.name}"
            )
        generated_path = output_dir / "charts" / path.name
        if not _same_pixels(generated_path, path):
            raise PublicationReproductionError(
                f"canonical chart pixels differ: {path.name}"
            )
        if (
            platform.system() == "Linux"
            and generated_path.read_bytes() != path.read_bytes()
        ):
            raise PublicationReproductionError(
                f"canonical chart bytes differ: {path.name}"
            )


def _validate_article(
    article: str,
    facts: Mapping[str, Any],
    snapshot: Mapping[str, Any],
    manifest: Mapping[str, Any],
    profile: Mapping[str, Any],
) -> None:
    seo = _mapping(manifest, "seo")
    title = _string(seo, "title")
    description = _string(seo, "meta_description")
    if (
        f'title: "{title}"' not in article
        or f'description: "{description}"' not in article
        or f"# {title}" not in article
    ):
        raise PublicationReproductionError("article SEO facts drifted")
    flow = profile.get("required_flow")
    if not isinstance(flow, list):
        raise PublicationReproductionError("publication profile is invalid")
    headings = [f"## {heading}" for heading in flow]
    if any(heading not in article for heading in headings) or [
        article.index(heading) for heading in headings
    ] != sorted(article.index(heading) for heading in headings):
        raise PublicationReproductionError("article buyer flow drifted")

    rows = _list_of_mappings(facts, "rows")
    result_rows = _markdown_table_rows(
        article, "| Tested path | BTC/USDT required fields |"
    )
    expected_results = [
        [
            f"{row['provider_name']} / QVeris Access Path",
            f"Sample passed, {row['positive']['passed']}/{row['positive']['total']}",
            "Rejected, "
            f"{row['invalid_input']['passed']}/{row['invalid_input']['total']}",
            f"{round(float(row['latency_median_ms']))} ms",
            "1 credit/call",
            _expected_links(row, manifest),
        ]
        for row in rows
    ]
    if result_rows != expected_results:
        if any("Native API" in cell for row in result_rows for cell in row):
            raise PublicationReproductionError(
                "Provider and Access Path identity drifted"
            )
        expected_pages = {
            str(row["qveris_provider_page"]) for row in rows
        }
        observed_pages = {
            value
            for row in result_rows
            for cell in row
            for value in re.findall(r"https://qveris\.ai/providers/[^)]+", cell)
        }
        if observed_pages != expected_pages:
            raise PublicationReproductionError("QVeris CTA drifted")
        raise PublicationReproductionError("article result table drifted")

    pricing_rows = _markdown_table_rows(
        article, "| Provider × Access Path | Official pricing fact |"
    )
    official_source_labels = {
        "Binance": "Binance Spot API market data",
        "OKX": "OKX market ticker API",
    }
    expected_pricing = []
    for row in rows:
        pricing = _mapping(row, "official_pricing")
        provider_name = str(row["provider_name"])
        expected_pricing.append(
            [
                f"{provider_name} / QVeris Access Path",
                f"{pricing['free_tier']} {pricing['paid_plans']}",
                str(pricing["verified_at"]),
                f"[{official_source_labels[provider_name]}]({pricing['pricing_url']})",
            ]
        )
    if pricing_rows != expected_pricing:
        raise PublicationReproductionError("official pricing facts drifted")

    agent_rows = _markdown_table_rows(
        article, "| Provider × Access Path | Returned identity |"
    )
    expected_agent = [
        [
            "Binance / QVeris Access Path",
            "`BTCUSDT` matched, 3/3",
            "Provider rejected, 3/3",
            "`price`, `open`, `high`, `low`, 3/3",
            "`symbol=BTCUSDT`",
            "Pagination and constrained Agent Trial",
        ],
        [
            "OKX / QVeris Access Path",
            "CAP-normalized `BTCUSDT` matched, 3/3",
            "Provider rejected, 3/3",
            "`price`, `open`, `high`, `low`, 3/3",
            "`instId=BTC-USDT`",
            "Pagination and constrained Agent Trial",
        ],
    ]
    if agent_rows != expected_agent:
        raise PublicationReproductionError("Agent interface facts drifted")

    release = _mapping(facts, "release")
    expected_fastest = _mapping(
        _mapping(facts, "recommendations"), "fastest_observed_path"
    )
    lower_latency_claims = re.findall(
        r"(Binance|OKX) was the lower-latency path", article
    )
    wrong_latency_claims = [
        name
        for name in lower_latency_claims
        if name != expected_fastest.get("provider_name")
    ]
    if wrong_latency_claims:
        if lower_latency_claims.count(str(expected_fastest["provider_name"])) == 1:
            raise PublicationReproductionError("unexpected material claim")
        raise PublicationReproductionError("selection advice drifted")
    required_claims = (
        f"This edition ran {facts['total_live_calls']} live calls "
        f"on {facts['edition']}",
        "OKX was the lower-latency path in this small test",
        "Both paths had the same public QVeris Inspect price on 2026-08-13: "
        "1 credit/call.",
        str(release["release_digest"]),
    )
    if any(article.count(claim) != 1 for claim in required_claims):
        raise PublicationReproductionError("article facts drifted")
    live_call_values = [
        int(value) for value in re.findall(r"(\d+) live calls", article)
    ]
    if live_call_values != [12, 12]:
        if any(value != 12 for value in live_call_values):
            raise PublicationReproductionError("unexpected material claim")
        raise PublicationReproductionError("article facts drifted")
    if any(
        value != release["release_digest"]
        for value in re.findall(r"sha256:[a-f0-9]{64}", article)
    ):
        raise PublicationReproductionError("unexpected material claim")
    for value in re.findall(r"(\d+(?:\.\d+)?) credits?/call", article):
        if float(value) != 1:
            raise PublicationReproductionError("unexpected material claim")
    if snapshot.get("total_live_calls") != facts.get("total_live_calls"):
        raise PublicationReproductionError("article facts drifted")


def _validate_links(article: str, manifest: Mapping[str, Any]) -> None:
    seo = _mapping(manifest, "seo")
    allowlist: set[str] = set()
    for key in (
        "supplier_sites",
        "provider_pages",
        "official_sources",
        "related_guides",
    ):
        allowlist.update(str(value) for value in _mapping(seo, key).values())
    github_links = seo.get("github_links")
    if not isinstance(github_links, list):
        raise PublicationReproductionError("publication GitHub links are invalid")
    allowlist.update(str(value) for value in github_links)
    observed = set(re.findall(r"\[[^]]+\]\((https://[^)]+)\)", article))
    if observed != allowlist:
        unknown = observed - allowlist
        if any("qveris.ai/providers/okx" in value for value in unknown):
            raise PublicationReproductionError("QVeris CTA drifted")
        raise PublicationReproductionError(
            "article external links differ from allowlist"
        )
    if re.search(r"(?:file://|/Users/|/home/|[A-Za-z]:\\)", article):
        raise PublicationReproductionError("article contains a local path")


def _expected_links(row: Mapping[str, Any], manifest: Mapping[str, Any]) -> str:
    seo = _mapping(manifest, "seo")
    name = str(row["provider_name"])
    return (
        f"[{name}]({_mapping(seo, 'supplier_sites')[name]}) · "
        f"[Try it in QVeris]({_mapping(seo, 'provider_pages')[name]})"
    )


def _markdown_table_rows(article: str, header: str) -> list[list[str]]:
    lines = article.splitlines()
    try:
        start = next(
            index for index, line in enumerate(lines) if line.startswith(header)
        )
    except StopIteration as exc:
        raise PublicationReproductionError("required article table is missing") from exc
    rows: list[list[str]] = []
    for line in lines[start + 2 :]:
        if not line.startswith("|"):
            break
        rows.append([cell.strip() for cell in line.strip().strip("|").split("|")])
    return rows


def _case_cells(
    cells: list[Mapping[str, Any]], case_id: str
) -> list[Mapping[str, Any]]:
    return sorted(
        [cell for cell in cells if cell.get("case_id") == case_id],
        key=lambda cell: int(cast(int, cell["round"])),
    )


def _unique_by(
    values: list[Mapping[str, Any]], key: str, label: str
) -> dict[str, Mapping[str, Any]]:
    result: dict[str, Mapping[str, Any]] = {}
    for value in values:
        identity = _string(value, key)
        if identity in result:
            raise PublicationReproductionError(f"{label} contains duplicate identities")
        result[identity] = value
    return result


def _same_pixels(left_path: Path, right_path: Path) -> bool:
    with Image.open(left_path) as left_image, Image.open(right_path) as right_image:
        left = left_image.convert("RGBA")
        right = right_image.convert("RGBA")
        return (
            left.size == right.size
            and ImageChops.difference(left, right).getbbox() is None
        )


def _json_mapping(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PublicationReproductionError(f"invalid {label}") from exc
    if not isinstance(value, dict):
        raise PublicationReproductionError(f"invalid {label}")
    return value


def _list_of_mappings(document: Mapping[str, Any], key: str) -> list[Mapping[str, Any]]:
    value = document.get(key)
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        raise PublicationReproductionError(f"{key} must be a list of mappings")
    return cast(list[Mapping[str, Any]], value)


def _mapping(document: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    value = document.get(key)
    if not isinstance(value, Mapping):
        raise PublicationReproductionError(f"{key} must be a mapping")
    return cast(Mapping[str, Any], value)


def _string(document: Mapping[str, Any], key: str) -> str:
    value = document.get(key)
    if not isinstance(value, str) or not value:
        raise PublicationReproductionError(f"{key} must be a non-empty string")
    return value


def _artifact(root: Path, artifacts: Mapping[str, Any], key: str) -> Path:
    return resolve_repository_path(root, _string(artifacts, key))


def _file_digest(path: Path) -> str:
    return _digest(path.read_bytes())


def _digest(content: bytes) -> str:
    return f"sha256:{hashlib.sha256(content).hexdigest()}"


def _compact_json_bytes(document: Mapping[str, Any]) -> bytes:
    return (
        json.dumps(document, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        + "\n"
    ).encode()
