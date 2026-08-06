from pathlib import Path

import pytest

from qveris_bench.cli import parse_qveris_parameters, public_discovery_summary


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
                    "params": [
                        {
                            "name": "symbol",
                            "type": "string",
                            "required": True,
                            "description": "unreviewed provider text",
                            "example": "sensitive sample",
                        }
                    ],
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


def test_ac2_discovery_workflow_does_not_interpolate_manual_inputs_into_shell() -> None:
    workflow = Path(".github/workflows/qveris-discovery.yml").read_text()

    assert "DISCOVERY_QUERY: ${{ inputs.query }}" in workflow
    assert "DISCOVERY_LIMIT: ${{ inputs.limit }}" in workflow
    assert '"${{ inputs.query }}"' not in workflow
    assert '"${{ inputs.limit }}"' not in workflow
    assert '"$DISCOVERY_QUERY"' in workflow
    assert '"$DISCOVERY_LIMIT"' in workflow


def test_ac3_qveris_execute_parameters_require_a_json_object() -> None:
    assert parse_qveris_parameters('{"symbol":"SPY"}') == {"symbol": "SPY"}
    with pytest.raises(ValueError, match="JSON object"):
        parse_qveris_parameters("[]")
