import asyncio
import json
import os
from dataclasses import dataclass
from pathlib import Path

import pytest

from qveris_bench.evidence.store import PublicArtifactStore, RawArtifactStore
from qveris_bench.execution.errors import TransportError
from qveris_bench.execution.mcp import McpAdapter
from qveris_bench.execution.streamable_mcp import streamable_mcp_session

ROOT = Path(__file__).resolve().parents[2]
_ENDPOINT = "https://mcp.wind.com.cn/vserver_stock_data/mcp/"
_ACCESS_PATH_ID = "wind-stock-data-native-mcp"
_CANONICAL_TOOL = "get_stock_price_indicators"
_ARGUMENTS = {"windcode": "600519.SH", "indexes": "最新成交价"}


@dataclass(frozen=True)
class _TerminalEvidence:
    raw_digest: str
    public_digest: str
    outcome: str
    reason: str | None


def _validate_frozen_contract(
    endpoint: str, tool_name: str, arguments: dict[str, str]
) -> None:
    if endpoint != _ENDPOINT:
        raise AssertionError("live Wind endpoint does not match frozen contract")
    if tool_name != _CANONICAL_TOOL:
        raise AssertionError("live Wind tool does not match frozen contract")
    if arguments != _ARGUMENTS:
        raise AssertionError("live Wind arguments do not match frozen contract")


def _safe_terminal_reason(payload: object) -> str | None:
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    return None if "最新成交价" in serialized else "requested_indicator_missing"


def _persist_terminal_evidence(
    root: Path, raw_digest: str, reason: str | None
) -> _TerminalEvidence:
    outcome = "completed" if reason is None else "provider_negative"
    content = (
        json.dumps(
            {
                "access_path_id": _ACCESS_PATH_ID,
                "canonical_tool": _CANONICAL_TOOL,
                "outcome": outcome,
                "raw_digest": raw_digest,
                "reason": reason,
                "redaction_status": "sanitized",
                "disclosure_level": "sanitized_public",
                "license_status": "cleared",
            },
            sort_keys=True,
        )
        + "\n"
    ).encode()
    artifact = PublicArtifactStore(root).persist("wind-native-mcp-terminal", content)
    return _TerminalEvidence(
        raw_digest=raw_digest,
        public_digest=artifact.digest,
        outcome=outcome,
        reason=reason,
    )


def _persist_terminal_manifest(root: Path, evidence: _TerminalEvidence) -> None:
    payload = {
        "completed": int(evidence.outcome == "completed"),
        "provider_negative": int(evidence.outcome == "provider_negative"),
        "access_path_id": _ACCESS_PATH_ID,
        "canonical_tool": _CANONICAL_TOOL,
        "public_digest": evidence.public_digest,
        "redaction_status": "sanitized",
        "disclosure_level": "sanitized_public",
        "license_status": "cleared",
    }
    PublicArtifactStore(root).persist(
        "wind-native-mcp-terminal-manifest",
        (json.dumps(payload, sort_keys=True) + "\n").encode(),
    )


@pytest.mark.skipif(
    os.environ.get("RUN_LIVE_WIND_NATIVE_MCP") != "1",
    reason="live Wind native MCP run is disabled",
)
def test_ac2_live_wind_native_mcp_produces_safe_terminal_evidence(
    tmp_path: Path,
) -> None:
    api_key = os.environ.get("WIND_API_KEY")
    if not api_key:
        pytest.skip("WIND_API_KEY is required for the live Wind MCP run")
    public_root = Path(os.environ.get("LIVE_PUBLIC_EVIDENCE_ROOT", tmp_path / "public"))
    _validate_frozen_contract(_ENDPOINT, _CANONICAL_TOOL, _ARGUMENTS)

    async def run() -> _TerminalEvidence:
        async with streamable_mcp_session(_ENDPOINT, api_key) as session:
            adapter = McpAdapter(
                session,
                _CANONICAL_TOOL,
                RawArtifactStore(tmp_path / "raw", ROOT),
            )
            try:
                result = await adapter.invoke("wind-native-mcp-600519", _ARGUMENTS)
            except TransportError as exc:
                if exc.code == "mcp_tool_error":
                    return _persist_terminal_evidence(
                        public_root, exc.evidence_digest or "unavailable", "tool_error"
                    )
                raise AssertionError("native MCP transport did not complete") from None
        payload = json.loads(result.raw_path.read_text(encoding="utf-8"))
        return _persist_terminal_evidence(
            public_root, result.raw_digest, _safe_terminal_reason(payload)
        )

    evidence = asyncio.run(run())
    _persist_terminal_manifest(public_root, evidence)
    assert evidence.public_digest != evidence.raw_digest


def test_ac2_live_wind_native_mcp_rejects_redirected_contract() -> None:
    with pytest.raises(AssertionError, match="endpoint"):
        _validate_frozen_contract(
            "https://other.example/mcp", _CANONICAL_TOOL, _ARGUMENTS
        )
    with pytest.raises(AssertionError, match="tool"):
        _validate_frozen_contract(_ENDPOINT, "other-tool", _ARGUMENTS)
    with pytest.raises(AssertionError, match="arguments"):
        _validate_frozen_contract(
            _ENDPOINT, _CANONICAL_TOOL, {"windcode": "AAPL.O", "indexes": "最新成交价"}
        )


def test_ac3_live_wind_native_mcp_uses_value_free_terminal_categories() -> None:
    assert _safe_terminal_reason({"content": [{"text": "最新成交价: 1"}]}) is None
    assert _safe_terminal_reason({"content": [{"text": "no indicator"}]}) == (
        "requested_indicator_missing"
    )


def test_ac3_live_wind_native_mcp_terminal_artifacts_are_safe(tmp_path: Path) -> None:
    evidence = _persist_terminal_evidence(
        tmp_path, "sha256:" + "a" * 64, "requested_indicator_missing"
    )
    _persist_terminal_manifest(tmp_path, evidence)

    terminal = next(tmp_path.glob("wind-native-mcp-terminal-*.json")).read_text()
    manifest = next(
        tmp_path.glob("wind-native-mcp-terminal-manifest-*.json")
    ).read_text()
    assert "requested_indicator_missing" in terminal
    assert "最新成交价" not in terminal
    assert '"provider_negative": 1' in manifest
    assert evidence.raw_digest not in manifest
