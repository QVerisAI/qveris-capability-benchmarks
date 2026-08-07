from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

import httpx
import pytest

from qveris_bench.agents.base import AgentTrial
from qveris_bench.agents.frozen import FrozenAgentInputError, merge_frozen_parameters
from qveris_bench.agents.gateway import qveris_responses_client
from qveris_bench.evidence.hashing import sha256_digest
from qveris_bench.evidence.store import PublicArtifactStore, RawArtifactStore
from qveris_bench.execution.base import AdapterResult
from qveris_bench.execution.qveris import QverisToolClient, execute_discovered_tool
from qveris_bench.execution.qveris_binding import (
    load_registered_qveris_direct_binding,
)
from qveris_bench.models.suite import AgentProtocol

ROOT = Path(__file__).resolve().parents[2]
BINDINGS_REGISTRY = ROOT / "cap_packs/qveris-direct-bindings-stock-quote-family.json"
CANONICAL_BINDING_ID = "finnhub-600519-agent-family"
CANONICAL_TOOL = "stock-quote-canonical"
CANONICAL_PROMPT = "获取贵州茅台当前价格和报价时间"


def _canonical_input_schema() -> dict[str, object]:
    return {
        "type": "object",
        "properties": {"symbol": {"type": "string", "enum": ["600519.SH"]}},
        "required": ["symbol"],
        "additionalProperties": False,
    }


def test_ac8_agent_contract_accepts_only_the_canonical_symbol() -> None:
    binding = load_registered_qveris_direct_binding(
        BINDINGS_REGISTRY, CANONICAL_BINDING_ID
    )
    assert binding.parameters == {"symbol": "600519.SH"}

    assert merge_frozen_parameters(
        binding.parameters, {"symbol": "600519.SH"}, ("symbol",)
    ) == {"symbol": "600519.SH"}
    with pytest.raises(FrozenAgentInputError, match="outside the frozen run"):
        merge_frozen_parameters(binding.parameters, {"symbol": "AAPL"}, ("symbol",))


@pytest.mark.skipif(
    os.environ.get("RUN_LIVE_STOCK_QUOTE_FAMILY_AGENT") != "1",
    reason="live stock quote family agent run is disabled",
)
def test_ac8_live_agent_resolves_cn_request_with_one_canonical_call(
    tmp_path: Path,
) -> None:
    api_key = os.environ.get("QVERIS_API_KEY")
    if not api_key:
        pytest.skip("QVERIS_API_KEY is required for the live agent run")
    public_root = Path(
        os.environ.get(
            "LIVE_PUBLIC_EVIDENCE_ROOT", tmp_path / "stock-quote-family-agent-evidence"
        )
    )
    binding = load_registered_qveris_direct_binding(
        BINDINGS_REGISTRY, CANONICAL_BINDING_ID
    )
    binding_digest = sha256_digest(
        json.dumps(
            binding.model_dump(mode="json"), sort_keys=True, separators=(",", ":")
        ).encode()
    )
    registry_digest = sha256_digest(BINDINGS_REGISTRY.read_bytes())

    async def run() -> None:
        tool_client = QverisToolClient(
            httpx.AsyncClient(), RawArtifactStore(tmp_path, ROOT), api_key
        )

        async def invoke(arguments: dict[str, object]) -> object:
            try:
                parameters = merge_frozen_parameters(
                    binding.parameters, arguments, ("symbol",)
                )
            except FrozenAgentInputError as exc:
                return {"frozen_contract_error": str(exc)}
            return (
                await execute_discovered_tool(
                    tool_client,
                    "agent-stock-quote-cn-search",
                    binding.discovery_query,
                    binding.tool_id,
                    parameters,
                )
            ).result

        protocol = AgentProtocol(
            model=os.environ.get("QVERIS_AGENT_MODEL", "deepseek-v4-flash"),
            prompt_version="1.0.0",
            canonical_tool=CANONICAL_TOOL,
            maximum_calls=1,
            token_budget=512,
            timeout_seconds=60,
        )
        try:
            trace = await AgentTrial(
                qveris_responses_client(api_key),
                protocol,
                _canonical_input_schema(),
                invoke,
            ).run(CANONICAL_PROMPT)
        finally:
            await tool_client.close()

        assert trace.calls == 1
        if isinstance(trace.tool_result, AdapterResult):
            outcome = "single_call_completed"
            raw_digest = trace.tool_result.raw_digest
            assert trace.tool_result.raw_path.is_file()
        else:
            outcome = "argument_fidelity_violation"
            raw_digest = ""
            assert isinstance(trace.tool_result, dict)
            assert "frozen_contract_error" in trace.tool_result
        manifest = (
            json.dumps(
                {
                    "binding_id": CANONICAL_BINDING_ID,
                    "canonical_tool": CANONICAL_TOOL,
                    "prompt": CANONICAL_PROMPT,
                    "calls": trace.calls,
                    "elapsed_seconds": round(trace.elapsed_seconds, 3),
                    "output_tokens": trace.output_tokens,
                    "proposed_arguments": trace.proposed_arguments,
                    "raw_digest": raw_digest,
                    "binding_digest": binding_digest,
                    "binding_registry_digest": registry_digest,
                    "github_run_id": os.environ.get("GITHUB_RUN_ID"),
                    "github_sha": os.environ.get("GITHUB_SHA"),
                    "outcome": outcome,
                    "redaction_status": "sanitized",
                    "disclosure_level": "sanitized_public",
                    "license_status": "cleared",
                },
                sort_keys=True,
            )
            + "\n"
        ).encode()
        artifact = PublicArtifactStore(public_root).persist(
            "stock-quote-family-agent-trace", manifest
        )
        assert artifact.digest.startswith("sha256:")

    asyncio.run(run())
