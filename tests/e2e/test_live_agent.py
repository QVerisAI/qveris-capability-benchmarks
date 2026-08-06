import asyncio
import json
import os
from pathlib import Path

import httpx
import pytest

from qveris_bench.agents.base import AgentTrial
from qveris_bench.agents.gateway import qveris_responses_client
from qveris_bench.evidence.store import RawArtifactStore
from qveris_bench.execution.base import AdapterResult
from qveris_bench.execution.qveris import QverisToolClient, execute_discovered_tool
from qveris_bench.execution.qveris_binding import load_registered_qveris_direct_binding
from qveris_bench.models.suite import AgentProtocol
from qveris_bench.outcomes.etf_holdings import extract_alpha_vantage_etf_holdings
from qveris_bench.outcomes.extractor import extract_observation

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.skipif(
    os.environ.get("RUN_LIVE_AGENT") != "1", reason="live agent run is disabled"
)
def test_ac_live_deepseek_flash_runs_one_alpha_etf_tool(tmp_path: Path) -> None:
    api_key = os.environ.get("QVERIS_API_KEY")
    if not api_key:
        pytest.skip("QVERIS_API_KEY is required for the live agent run")

    binding = load_registered_qveris_direct_binding(
        ROOT / "cap_packs/qveris-direct-bindings.json", "alpha-vantage-spy-holdings"
    )

    async def run() -> None:
        tool_client = QverisToolClient(
            httpx.AsyncClient(), RawArtifactStore(tmp_path, ROOT), api_key
        )

        async def invoke(arguments: dict[str, object]) -> object:
            return (
                await execute_discovered_tool(
                    tool_client,
                    "agent-alpha-vantage-search",
                    binding.discovery_query,
                    binding.tool_id,
                    arguments,
                )
            ).result

        protocol = AgentProtocol(
            model=os.environ.get("QVERIS_AGENT_MODEL", "deepseek-v4-flash"),
            prompt_version="1.0.0",
            canonical_tool="alpha_vantage_etf_profile",
            maximum_calls=1,
            token_budget=512,
            timeout_seconds=60,
        )
        try:
            trace = await AgentTrial(
                qveris_responses_client(api_key),
                protocol,
                {
                    "type": "object",
                    "properties": {"symbol": {"type": "string"}},
                    "required": ["symbol"],
                    "additionalProperties": False,
                },
                invoke,
            ).run("Retrieve the ETF holdings for SPY.")
        finally:
            await tool_client.close()

        assert trace.calls == 1
        assert trace.proposed_arguments == {"symbol": "SPY"}
        result = trace.tool_result
        assert isinstance(result, AdapterResult)
        assert result.raw_path.is_file()
        document = json.loads(result.raw_path.read_text(encoding="utf-8"))
        facts = extract_alpha_vantage_etf_holdings(document, "SPY")
        observation = extract_observation(
            ROOT / "cap_packs/etf_holdings/observation-schema.yaml",
            facts,
            result.raw_digest,
            "1.0.0",
        )
        assert observation.facts["holdings"]

    asyncio.run(run())
