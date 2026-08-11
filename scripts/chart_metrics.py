from __future__ import annotations

from typing import Any

AccessPathKey = tuple[str, str]


def direct_metrics_by_access_path(
    records: list[dict[str, Any]], paths: list[dict[str, Any]]
) -> dict[AccessPathKey, dict[str, float | None]]:
    metrics: dict[AccessPathKey, dict[str, float | None]] = {}
    for path in paths:
        key = (str(path["provider_id"]), str(path["access_path_id"]))
        cells = [
            record
            for record in records
            if (record.get("provider_id"), record.get("access_path_id")) == key
        ]
        # Match the article's success-call semantics: latency and cost come
        # from passed positive calls only; negative controls are not billed.
        passed_cells = [record for record in cells if record.get("state") == "passed"]
        latencies = [
            float(record["latency_ms"])
            for record in passed_cells
            if record.get("latency_ms") is not None
        ]
        costs = [
            float(record["cost_credits"])
            for record in passed_cells
            if isinstance(record.get("cost_credits"), (int, float))
            and record["cost_credits"] > 0
        ]
        metrics[key] = {
            "latency_ms": sum(latencies) / len(latencies) if latencies else None,
            "cost_credits": sum(costs) / len(costs) if costs else None,
        }
    return metrics
