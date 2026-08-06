from qveris_bench.cli import public_discovery_summary


def test_ac1_discovery_output_excludes_account_and_provider_raw_metadata() -> None:
    result = public_discovery_summary(
        [{"tool_id": "provider.quote", "name": "Quote", "description": "raw"}],
        {
            "remaining_credits": 12.5,
            "results": [
                {
                    "tool_id": "provider.quote",
                    "provider_id": "provider",
                    "provider_name": "Provider",
                    "params": [{"name": "symbol", "type": "string", "required": True}],
                    "expected_cost": "1",
                    "billing_rule": {"price": {"amount_credits": 1}},
                    "provider_description": "private provider text",
                }
            ],
        },
    )

    assert result == {
        "result_count": 1,
        "tools": [
            {
                "tool_id": "provider.quote",
                "name": "Quote",
                "provider_id": "provider",
                "provider_name": "Provider",
                "parameters": [{"name": "symbol", "type": "string", "required": True}],
                "expected_cost": "1",
            }
        ],
    }, "AC1 discovery logs must exclude account balances and unreviewed raw metadata"
