from __future__ import annotations

from pathlib import Path

import pytest

from qveris_bench.cli import public_discovery_summary
from qveris_bench.execution.qveris import public_response_shape


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
                        }
                    ],
                    "expected_cost": "1",
                }
            ],
        },
        "sha256:" + "a" * 64,
    )

    assert result["tools"] == [
        {
            "tool_id": "provider.quote",
            "name": "Quote",
            "provider_id": "provider",
            "provider_name": "Provider",
            "parameters": [{"name": "symbol", "type": "string", "required": True}],
            "expected_cost": "1",
        }
    ], "AC1 discovery output must retain only sanitized tool metadata"


@pytest.mark.parametrize("digest", ["not-a-digest", "sha256:" + "a" * 63])
def test_ac1_discovery_output_rejects_invalid_evidence_digest(digest: str) -> None:
    with pytest.raises(ValueError, match="digest"):
        public_discovery_summary([], {}, digest)


def test_ac2_response_shape_recurses_into_json_encoded_provider_data() -> None:
    assert public_response_shape('{"close": 201.0, "symbol": "AAPL"}', depth=2) == {
        "type": "json_string",
        "value_shape": {
            "type": "object",
            "keys": ["symbol"],
            "field_count": 2,
            "fields": {"symbol": {"type": "string"}},
        },
    }


def test_ac3_discovery_workflow_does_not_interpolate_manual_inputs_into_shell() -> None:
    workflow = Path(".github/workflows/qveris-discovery.yml").read_text()

    assert "DISCOVERY_QUERY: ${{ inputs.query }}" in workflow
    assert '"$DISCOVERY_QUERY"' in workflow
