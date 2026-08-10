from scripts import chart_metrics


def test_ac5_chart_metrics_never_merge_two_access_paths_for_one_provider() -> None:
    records = [
        {
            "provider_id": "example-provider",
            "access_path_id": "example-native",
            "latency_ms": 100,
            "cost_credits": None,
        },
        {
            "provider_id": "example-provider",
            "access_path_id": "example-qveris",
            "latency_ms": 900,
            "cost_credits": 2,
        },
    ]
    paths = [
        {
            "provider_id": "example-provider",
            "access_path_id": "example-native",
        },
        {
            "provider_id": "example-provider",
            "access_path_id": "example-qveris",
        },
    ]

    metrics = chart_metrics.direct_metrics_by_access_path(records, paths)

    assert metrics[("example-provider", "example-native")]["latency_ms"] == 100
    assert metrics[("example-provider", "example-qveris")]["latency_ms"] == 900
    assert metrics[("example-provider", "example-native")]["cost_credits"] is None
    assert metrics[("example-provider", "example-qveris")]["cost_credits"] == 2
