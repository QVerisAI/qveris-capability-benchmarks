import asyncio
import json
import os
from dataclasses import dataclass
from pathlib import Path

import httpx
import pytest

from qveris_bench.evidence.store import PublicArtifactStore, RawArtifactStore
from qveris_bench.execution.qveris import QverisToolClient, execute_discovered_tool
from qveris_bench.execution.qveris_binding import (
    load_registered_qveris_direct_binding,
    validate_qveris_direct_binding,
)
from qveris_bench.outcomes.etf_holdings import (
    EtfHoldingsExtractionError,
    extract_alpha_vantage_etf_holdings,
)
from qveris_bench.outcomes.extractor import ExtractionError, extract_observation
from qveris_bench.suites.compiler import compile_suite

ROOT = Path(__file__).resolve().parents[2]
EXPECTED = {
    "alpha-vantage-spy-holdings": (
        "alpha-vantage-etf-holdings",
        "alpha-vantage",
        "alphavantage.etf.profile.retrieve.v1.467a92c0",
        False,
    ),
    "alpha-vantage-invalid-etf": (
        "alpha-vantage-etf-holdings",
        "alpha-vantage",
        "alphavantage.etf.profile.retrieve.v1.467a92c0",
        True,
    ),
    "fiu-spy-holdings": (
        "fiu-etf-holdings",
        "fiu",
        "fiu_mcp_server.postapiusf10fundconstituent.create.v2.30b6ab72",
        False,
    ),
    "fiu-invalid-etf": (
        "fiu-etf-holdings",
        "fiu",
        "fiu_mcp_server.postapiusf10fundconstituent.create.v2.30b6ab72",
        True,
    ),
}


@dataclass(frozen=True)
class TerminalEvidence:
    binding_id: str
    run_key: str
    raw_digest: str
    public_digest: str
    outcome: str
    reason: str | None


def validate_fixed_binding(binding_id: str, binding: object) -> tuple[bool, str]:
    expected = EXPECTED.get(binding_id)
    if expected is None:
        raise AssertionError("live ETF binding is not allowlisted")
    if (
        binding.suite_id != "etf-holdings-v1"
        or binding.access_path_id != expected[0]
        or binding.provider_id != expected[1]
        or binding.tool_id != expected[2]
    ):
        raise AssertionError("live ETF binding does not match frozen contract")
    return expected[3], expected[1]


def semantic_reason(
    provider_id: str, document: object, symbol: str, negative: bool
) -> str | None:
    if provider_id != "alpha-vantage":
        return "extractor_not_available"
    try:
        facts = extract_alpha_vantage_etf_holdings(
            document, symbol, negative_control=negative
        )
        extract_observation(
            ROOT / "cap_packs/etf_holdings/observation-schema.yaml",
            facts,
            "sha256:" + "a" * 64,
            "1.0.0",
            negative_control=negative,
        )
    except EtfHoldingsExtractionError as exc:
        message = str(exc)
        if "validation error" in message:
            return "invalid_negative_response"
        if "weight" in message:
            return "invalid_weight"
        if "holdings" in message:
            return "missing_holdings"
        return "unrecognized_provider_response"
    except ExtractionError:
        return "invalid_observation"
    return None


def persist_terminal_evidence(
    root: Path,
    binding_id: str,
    run_key: str,
    raw_digest: str,
    reason: str | None,
    suite_fingerprint: str,
) -> TerminalEvidence:
    outcome = "completed" if reason is None else "provider_negative"
    content = (
        json.dumps(
            {
                "binding_id": binding_id,
                "run_key": run_key,
                "outcome": outcome,
                "raw_digest": raw_digest,
                "reason": reason,
                "extractor_version": "1.0.0",
                "suite_fingerprint": suite_fingerprint,
                "redaction_status": "sanitized",
                "disclosure_level": "sanitized_public",
                "license_status": "cleared",
            },
            sort_keys=True,
        ).encode()
        + b"\n"
    )
    artifact = PublicArtifactStore(root).persist(binding_id, content)
    return TerminalEvidence(
        binding_id, run_key, raw_digest, artifact.digest, outcome, reason
    )


@pytest.mark.skipif(
    os.environ.get("RUN_LIVE_ETF_HOLDINGS") != "1",
    reason="live ETF holdings run is disabled",
)
def test_ac_live_etf_direct_produces_semantic_terminal_evidence(tmp_path: Path) -> None:
    api_key = os.environ.get("QVERIS_API_KEY")
    binding_id = os.environ.get("ETF_BINDING_ID")
    round_number = os.environ.get("ETF_ROUND")
    if not api_key or not binding_id or not round_number:
        pytest.skip("QVERIS_API_KEY, ETF_BINDING_ID, and ETF_ROUND are required")
    public_root = Path(os.environ.get("LIVE_PUBLIC_EVIDENCE_ROOT", tmp_path / "public"))
    suite_fingerprint = compile_suite(
        ROOT / "cap_packs/etf_holdings/suite.yaml",
        ROOT / "cap_packs/etf_holdings/cases.yaml",
        ROOT / "providers",
    ).fingerprint
    binding = load_registered_qveris_direct_binding(
        ROOT / "cap_packs/qveris-direct-bindings.json", binding_id
    )
    validate_qveris_direct_binding(
        binding, ROOT / "cap_packs/etf_holdings/suite.yaml", ROOT / "providers"
    )
    negative, provider_id = validate_fixed_binding(binding_id, binding)

    async def run() -> TerminalEvidence:
        client = QverisToolClient(
            httpx.AsyncClient(), RawArtifactStore(tmp_path, ROOT), api_key
        )
        try:
            result = await execute_discovered_tool(
                client,
                f"{binding_id}-search",
                binding.discovery_query,
                binding.tool_id,
                binding.parameters,
            )
            document = json.loads(result.result.raw_path.read_text(encoding="utf-8"))
            reason = semantic_reason(
                provider_id, document, str(binding.parameters["symbol"]), negative
            )
            return persist_terminal_evidence(
                public_root,
                binding_id,
                f"{binding_id}:direct:{round_number}",
                result.result.raw_digest,
                reason,
                suite_fingerprint,
            )
        finally:
            await client.close()

    evidence = asyncio.run(run())
    assert evidence.public_digest != evidence.raw_digest


def test_ac_live_etf_rejects_redirected_binding_before_execution() -> None:
    binding = load_registered_qveris_direct_binding(
        ROOT / "cap_packs/qveris-direct-bindings.json", "alpha-vantage-spy-holdings"
    )
    with pytest.raises(AssertionError, match="frozen contract"):
        validate_fixed_binding(
            "alpha-vantage-spy-holdings",
            binding.model_copy(update={"tool_id": "other.provider.tool"}),
        )


def test_ac_live_etf_terminal_evidence_is_safe(tmp_path: Path) -> None:
    record = persist_terminal_evidence(
        tmp_path,
        "alpha-vantage-spy-holdings",
        "alpha-vantage-spy-holdings:direct:1",
        "sha256:" + "a" * 64,
        "missing_holdings",
        "b" * 64,
    )
    assert record.outcome == "provider_negative"
    assert record.public_digest != record.raw_digest
    artifact = next(tmp_path.glob("alpha-vantage-spy-holdings-*.json")).read_text()
    assert "missing_holdings" in artifact
    assert '"suite_fingerprint": "' + "b" * 64 + '"' in artifact
