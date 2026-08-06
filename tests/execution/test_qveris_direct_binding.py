from pathlib import Path

import pytest

from qveris_bench.evidence.hashing import sha256_digest
from qveris_bench.execution.qveris_binding import (
    QverisDirectBindingError,
    load_qveris_direct_binding,
)
from qveris_bench.suites.fingerprint import canonical_json_bytes


def test_ac1_direct_binding_requires_its_frozen_digest(tmp_path: Path) -> None:
    path = tmp_path / "direct-binding.json"
    payload = {
        "version": "1.0.0",
        "access_path_id": "fiu-etf-holdings",
        "provider_id": "fiu",
        "discovery_query": "US ETF holdings",
        "discovery_digest": "sha256:" + "a" * 64,
        "tool_id": "fiu.tool.v1",
        "parameters": {"symbol": "SPY.US"},
    }
    path.write_bytes(canonical_json_bytes(payload))

    binding = load_qveris_direct_binding(
        path, sha256_digest(canonical_json_bytes(payload))
    )

    assert binding.tool_id == "fiu.tool.v1"
    with pytest.raises(QverisDirectBindingError, match="digest mismatch"):
        load_qveris_direct_binding(path, "sha256:" + "b" * 64)
