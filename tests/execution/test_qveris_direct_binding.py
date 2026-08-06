from pathlib import Path

import pytest

from qveris_bench.execution.qveris_binding import (
    QverisDirectBindingError,
    load_registered_qveris_direct_binding,
    validate_qveris_direct_binding,
)
from qveris_bench.suites.fingerprint import canonical_json_bytes


def test_ac1_direct_binding_must_belong_to_an_included_suite_path(
    tmp_path: Path,
) -> None:
    providers = tmp_path / "providers"
    provider_path = providers / "fiu" / "provider.yaml"
    provider_path.parent.mkdir(parents=True)
    provider_path.write_text(
        """provider:
  provider_id: fiu
  official_name: FIU
  website: https://example.com/
  testing_authorization: QVeris Direct Test
  qveris_integration: true
access_paths:
  - access_path_id: fiu-etf-holdings
    provider_id: fiu
    path_type: official_api
    credential_env: [QVERIS_API_KEY]
    official_source: https://example.com/docs
    canonical_interface: ETF_HOLDINGS
    agent_trial_eligible: false
    qualification:
      disposition: included
      reason: QVeris provides an attributable Direct path.
      evidence_digest: >-
        sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
"""
    )
    suite_path = tmp_path / "suite.yaml"
    suite_path.write_text(
        """suite_id: etf-holdings-v1
version: 1.0.0
cap_id: etf-holdings
cap_version: 1.0.0
case_ids: [spy-holdings]
access_path_ids: [fiu-etf-holdings]
modes: [direct]
rounds: 3
environment: {}
agent_protocol: null
not_applicable: []
"""
    )
    payload = {
        "binding_id": "fiu-spy-holdings",
        "suite_id": "etf-holdings-v1",
        "version": "1.0.0",
        "access_path_id": "fiu-etf-holdings",
        "provider_id": "fiu",
        "discovery_query": "US ETF holdings",
        "discovery_digest": "sha256:" + "a" * 64,
        "tool_id": "fiu.tool.v1",
        "parameters": {"symbol": "SPY.US"},
    }
    registry = tmp_path / "qveris-direct-bindings.json"
    registry.write_bytes(canonical_json_bytes({"bindings": [payload]}))
    binding = load_registered_qveris_direct_binding(registry, "fiu-spy-holdings")

    assert binding.tool_id == "fiu.tool.v1"
    validate_qveris_direct_binding(binding, suite_path, providers)
    suite_path.write_text(suite_path.read_text().replace("fiu-etf-holdings", "other"))
    with pytest.raises(QverisDirectBindingError, match="not in the frozen suite"):
        validate_qveris_direct_binding(binding, suite_path, providers)


def test_ac2_direct_execution_resolves_only_a_registered_binding(
    tmp_path: Path,
) -> None:
    registry = tmp_path / "qveris-direct-bindings.json"
    registry.write_bytes(
        canonical_json_bytes(
            {
                "bindings": [
                    {
                        "binding_id": "fiu-spy-holdings",
                        "suite_id": "etf-holdings-v1",
                        "version": "1.0.0",
                        "access_path_id": "fiu-etf-holdings",
                        "provider_id": "fiu",
                        "discovery_query": "US ETF holdings",
                        "discovery_digest": "sha256:" + "a" * 64,
                        "tool_id": "fiu.tool.v1",
                        "parameters": {"symbol": "SPY.US"},
                    }
                ]
            }
        )
    )

    binding = load_registered_qveris_direct_binding(registry, "fiu-spy-holdings")

    assert binding.tool_id == "fiu.tool.v1"
    with pytest.raises(QverisDirectBindingError, match="unknown binding"):
        load_registered_qveris_direct_binding(registry, "operator-supplied")
