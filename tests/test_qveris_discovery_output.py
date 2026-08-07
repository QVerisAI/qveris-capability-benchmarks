from pathlib import Path

import pytest
import yaml
from pytest import MonkeyPatch

from qveris_bench.cli import public_discovery_summary, qveris_repository_root


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
        "sha256:" + "a" * 64,
    )

    assert result == {
        "discovery_raw_digest": "sha256:" + "a" * 64,
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


@pytest.mark.parametrize("digest", ["not-a-digest", "sha256:" + "a" * 63])
def test_ac1_discovery_output_rejects_invalid_evidence_digest(digest: str) -> None:
    with pytest.raises(ValueError, match="digest"):
        public_discovery_summary([], {}, digest)


def test_ac2_discovery_workflow_does_not_interpolate_manual_inputs_into_shell() -> None:
    workflow = Path(".github/workflows/qveris-discovery.yml").read_text()

    assert "DISCOVERY_QUERY: ${{ inputs.query }}" in workflow
    assert "DISCOVERY_LIMIT: ${{ inputs.limit }}" in workflow
    assert '"${{ inputs.query }}"' not in workflow
    assert '"${{ inputs.limit }}"' not in workflow
    assert '"$DISCOVERY_QUERY"' in workflow
    assert '"$DISCOVERY_LIMIT"' in workflow


def test_ac3_direct_workflow_executes_only_fixed_registered_bindings() -> None:
    workflow = Path(".github/workflows/qveris-direct-e2e.yml").read_text()

    assert "environment: benchmark-e2e" in workflow
    assert "QVERIS_API_KEY: ${{ secrets.QVERIS_API_KEY }}" in workflow
    assert "inputs:" not in workflow
    assert "--binding-id ${{ matrix.binding_id }}" in workflow
    assert '--raw-artifact-dir "$RUNNER_TEMP/qveris-raw"' in workflow
    assert "--response-shape" not in workflow
    assert "qveris-finance" not in workflow
    assert workflow.count("alpha-vantage-spy-holdings") == 1
    assert workflow.count("fiu-spy-holdings") == 1
    assert "twelve-data-spy-holdings" not in workflow


def test_ac4_diagnostic_workflow_emits_shapes_for_fixed_bindings_only() -> None:
    workflow = Path(".github/workflows/qveris-direct-diagnostic.yml").read_text()

    assert "environment: benchmark-e2e" in workflow
    assert "inputs:" not in workflow
    assert "QVERIS_API_KEY: ${{ secrets.QVERIS_API_KEY }}" in workflow
    assert "--response-shape" in workflow
    assert workflow.count("alpha-vantage-spy-holdings") == 1
    assert workflow.count("fiu-spy-holdings") == 1
    assert "twelve-data-spy-holdings" not in workflow


def test_ac4_finnhub_diagnostic_limits_execution_to_quote_bindings() -> None:
    workflow_path = Path(".github/workflows/finnhub-quote-diagnostic.yml")
    workflow = workflow_path.read_text()
    document = yaml.safe_load(workflow_path.read_text())

    assert "environment: benchmark-e2e" in workflow
    assert "inputs:" not in workflow
    assert "QVERIS_API_KEY: ${{ secrets.QVERIS_API_KEY }}" in workflow
    assert "--response-shape" in workflow
    matrix = document["jobs"]["diagnostic"]["strategy"]["matrix"]
    assert set(matrix) == {"binding_id"}
    assert matrix["binding_id"] == [
        "finnhub-aapl-quote",
        "finnhub-invalid-stock",
    ]
    assert workflow.count("--binding-id") == 1


def test_ac5_direct_binding_policy_ignores_a_forged_current_directory(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    (tmp_path / "cap_packs").mkdir()
    (tmp_path / "cap_packs" / "qveris-direct-bindings.json").write_text("{}")
    monkeypatch.chdir(tmp_path)

    assert qveris_repository_root() != tmp_path


def test_ac6_diagnostic_cli_requests_nested_value_free_shape() -> None:
    source = Path("src/qveris_bench/cli.py").read_text()

    assert "public_response_shape(document, depth=4)" in source


def test_ac7_live_agent_workflow_uses_only_benchmark_secret_and_flash_model() -> None:
    workflow = Path(".github/workflows/live-agent-e2e.yml").read_text()

    assert "environment: benchmark-e2e" in workflow
    assert "QVERIS_API_KEY: ${{ secrets.QVERIS_API_KEY }}" in workflow
    assert "QVERIS_AGENT_MODEL: deepseek-v4-flash" in workflow
    assert 'RUN_LIVE_AGENT: "1"' in workflow
    assert "inputs:" not in workflow


def test_ac8_live_stock_quote_workflow_uses_only_fixed_qveris_bindings() -> None:
    workflow = Path(".github/workflows/live-stock-quote-e2e.yml").read_text()

    assert "environment: benchmark-e2e" in workflow
    assert "QVERIS_API_KEY: ${{ secrets.QVERIS_API_KEY }}" in workflow
    assert 'RUN_LIVE_STOCK_QUOTE: "1"' in workflow
    assert "inputs:" not in workflow
    assert "FINNHUB_API_KEY" not in workflow


def test_ac8_live_stock_quote_validates_frozen_binding_before_execution() -> None:
    source = Path("tests/e2e/test_live_stock_quote.py").read_text()

    assert "validate_qveris_direct_binding(" in source
    assert 'ROOT / "cap_packs/stock_quote/suite.yaml"' in source
    assert 'assert binding.access_path_id == "finnhub-stock-quote"' in source
    assert 'assert binding.provider_id == "finnhub"' in source


def test_ac9_live_etf_direct_workflow_has_a_fixed_twelve_call_matrix() -> None:
    workflow_path = Path(".github/workflows/live-etf-direct-e2e.yml")
    workflow = workflow_path.read_text()
    document = yaml.safe_load(workflow)

    assert "environment: benchmark-e2e" in workflow
    assert "QVERIS_API_KEY: ${{ secrets.QVERIS_API_KEY }}" in workflow
    assert "qveris-finance" not in workflow
    assert "stock-quote" not in workflow
    matrix = document["jobs"]["direct"]["strategy"]["matrix"]
    assert set(matrix) == {"binding_id", "round"}
    assert matrix["binding_id"] == [
        "alpha-vantage-spy-holdings",
        "alpha-vantage-invalid-etf",
        "fiu-spy-holdings",
        "fiu-invalid-etf",
    ]
    assert matrix["round"] == [1, 2, 3]
    assert "pytest tests/e2e/test_live_etf_holdings.py -q" in workflow
    assert "ETF_BINDING_ID: ${{ matrix.binding_id }}" in workflow
    assert "ETF_ROUND: ${{ matrix.round }}" in workflow
    assert "--binding-id" not in workflow


def test_ac9_live_etf_test_executes_only_the_matrix_binding() -> None:
    source = Path("tests/e2e/test_live_etf_holdings.py").read_text()

    assert 'binding_id = os.environ.get("ETF_BINDING_ID")' in source
    assert 'round_number = os.environ.get("ETF_ROUND")' in source
    assert 'f"{binding_id}:direct:{round_number}"' in source
    assert "for binding_id" not in source
