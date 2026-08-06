from pathlib import Path

import pytest

from qveris_bench.models.provider import AccessPath
from qveris_bench.suites.bindings import (
    ProviderBindingError,
    load_provider_bindings,
    validate_provider_bindings,
)


def _path() -> AccessPath:
    return AccessPath.model_validate(
        {
            "access_path_id": "fmp-etf-holdings",
            "provider_id": "financial-modeling-prep",
            "path_type": "official_api",
            "official_source": "https://financialmodelingprep.com/docs",
            "canonical_interface": "etf-holdings",
            "agent_trial_eligible": False,
        }
    )


def test_ac_bindings_must_match_the_resolved_provider_registry(tmp_path: Path) -> None:
    bindings = tmp_path / "provider-bindings.yaml"
    bindings.write_text(
        "access_paths:\n"
        "  - access_path_id: fmp-etf-holdings\n"
        "    provider_id: financial-modeling-prep\n"
        "    canonical_interface: etf-holdings\n"
        "    official_source: https://financialmodelingprep.com/docs\n"
    )

    validate_provider_bindings(load_provider_bindings(bindings), (_path(),))

    bindings.write_text(
        "access_paths:\n"
        "  - access_path_id: fmp-etf-holdings\n"
        "    provider_id: another-provider\n"
        "    canonical_interface: etf-holdings\n"
        "    official_source: https://financialmodelingprep.com/docs\n"
    )
    with pytest.raises(ProviderBindingError, match="registry"):
        validate_provider_bindings(load_provider_bindings(bindings), (_path(),))
