from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

import httpx
import pytest

from qveris_bench.cap_packs.dividend_events.direct import (
    DividendDirectResult,
    evaluate_dividend_document,
)
from qveris_bench.evidence.store import PublicArtifactStore, RawArtifactStore
from qveris_bench.execution.direct_binding import (
    DirectBinding,
    direct_binding_registry_digest,
    load_direct_binding_registry,
    validate_direct_binding_registry,
)
from qveris_bench.execution.mcp import McpAdapter
from qveris_bench.execution.qveris import (
    QverisToolClient,
    execute_discovered_tool,
    gateway_metrics,
)
from qveris_bench.execution.streamable_mcp import streamable_mcp_session
from qveris_bench.models.enums import AccessPathType, CellState
from qveris_bench.providers.repository import ProviderRegistryRepository
from qveris_bench.suites.compiler import compile_suite

ROOT = Path(__file__).resolve().parents[2]
PACK = ROOT / "cap_packs/dividend_events"
REGISTRY_PATH = PACK / "direct-bindings.json"


def _selected_cell(binding: DirectBinding, round_number: int):
    compiled = compile_suite(
        PACK / "suite.yaml", PACK / "cases.yaml", ROOT / "providers"
    )
    matches = [
        cell
        for cell in compiled.run_plan.cells
        if cell.case_id == binding.case_id
        and cell.access_path_id == binding.access_path_id
        and cell.round == round_number
        and cell.applicable
    ]
    if len(matches) != 1:
        raise AssertionError("binding must resolve to one applicable frozen RunCell")
    case = next(case for case in compiled.cases if case.case_id == binding.case_id)
    return compiled, case, matches[0]


def _access_path(binding: DirectBinding):
    paths = {
        path.access_path_id: path
        for record in ProviderRegistryRepository(ROOT / "providers").cohort_check()
        for path in record.access_paths
    }
    return paths[binding.access_path_id]


def _public_terminal_payload(
    binding: DirectBinding,
    run_key: str,
    raw_digest: str,
    result: DividendDirectResult,
    suite_fingerprint: str,
    registry_digest: str,
    latency_ms: float | None,
    cost_credits: float | None,
) -> bytes:
    return (
        json.dumps(
            {
                "binding_id": binding.binding_id,
                "run_key": run_key,
                "provider_id": binding.provider_id,
                "access_path_id": binding.access_path_id,
                "transport": binding.transport,
                "state": result.state,
                "facts": result.facts,
                "unmet_conditions": result.unmet_conditions,
                "failure_attribution": result.failure_attribution,
                "raw_digest": raw_digest,
                "binding_registry_digest": registry_digest,
                "extractor_version": "1.0.0",
                "suite_fingerprint": suite_fingerprint,
                "redaction_status": "sanitized",
                "disclosure_level": "sanitized_public",
                "license_status": "cleared",
                "latency_ms": latency_ms,
                "cost_credits": cost_credits,
                "github_run_id": os.environ.get("GITHUB_RUN_ID"),
                "github_sha": os.environ.get("GITHUB_SHA"),
            },
            sort_keys=True,
        )
        + "\n"
    ).encode()


@pytest.mark.skipif(
    os.environ.get("RUN_LIVE_DIVIDEND_EVENTS") != "1",
    reason="live dividend events run is disabled",
)
def test_ac8_live_mixed_direct_path_produces_safe_terminal_evidence(
    tmp_path: Path,
) -> None:
    binding_id = os.environ.get("DIVIDEND_BINDING_ID")
    round_value = os.environ.get("DIVIDEND_ROUND")
    if not binding_id or not round_value:
        pytest.skip("live dividend binding environment is incomplete")
    registry = load_direct_binding_registry(REGISTRY_PATH)
    validate_direct_binding_registry(
        registry,
        PACK / "suite.yaml",
        PACK / "cases.yaml",
        ROOT / "providers",
    )
    binding = next(
        item for item in registry.bindings if item.binding_id == binding_id
    )
    compiled, case, cell = _selected_cell(binding, int(round_value))
    public_root = Path(os.environ.get("LIVE_PUBLIC_EVIDENCE_ROOT", tmp_path / "public"))
    raw_store = RawArtifactStore(tmp_path / "raw", ROOT)

    async def run():
        if binding.transport is AccessPathType.QVERIS_CONNECTOR:
            api_key = os.environ.get("QVERIS_API_KEY")
            if not api_key:
                pytest.skip("QVERIS_API_KEY is required")
            client = QverisToolClient(httpx.AsyncClient(), raw_store, api_key)
            try:
                execution = await execute_discovered_tool(
                    client,
                    f"{binding.binding_id}-round-{round_value}-search",
                    str(binding.discovery_query),
                    binding.tool_id,
                    binding.parameters,
                )
            finally:
                await client.close()
            document = json.loads(execution.result.raw_path.read_text())
            latency_ms, cost_credits = gateway_metrics(document)
            return execution.result, document, latency_ms, cost_credits

        api_key = os.environ.get("IFIND_MCP_API_KEY")
        if not api_key:
            pytest.skip("IFIND_MCP_API_KEY is required")
        path = _access_path(binding)
        if path.endpoint_url is None:
            raise AssertionError("Native MCP endpoint is required")
        async with streamable_mcp_session(
            str(path.endpoint_url), api_key, bearer=False
        ) as session:
            result = await McpAdapter(session, binding.tool_id, raw_store).invoke(
                f"{binding.binding_id}-round-{round_value}", binding.parameters
            )
        document = json.loads(result.raw_path.read_text())
        return result, document, None, None

    adapter_result, document, latency_ms, cost_credits = asyncio.run(run())
    terminal = evaluate_dividend_document(
        str(binding.provider_id),
        document,
        case,
        PACK / "observation-schema.yaml",
        adapter_result.raw_digest,
    )
    content = _public_terminal_payload(
        binding,
        cell.run_key,
        adapter_result.raw_digest,
        terminal,
        compiled.fingerprint,
        direct_binding_registry_digest(REGISTRY_PATH),
        latency_ms,
        cost_credits,
    )
    public = PublicArtifactStore(public_root).persist(
        f"{binding.binding_id}-round-{round_value}-terminal", content
    )
    assert public.digest != adapter_result.raw_digest


def test_ac8_public_terminal_excludes_credentials_and_request_parameters() -> None:
    binding = load_direct_binding_registry(REGISTRY_PATH).bindings[0]
    content = _public_terminal_payload(
        binding,
        "run-key",
        "sha256:" + "a" * 64,
        DividendDirectResult(
            state=CellState.COMPLETED,
            facts={"symbol": "600519.SH", "amount": 1.0},
            unmet_conditions=(),
            failure_attribution=None,
        ),
        "b" * 64,
        "sha256:" + "c" * 64,
        None,
        None,
    ).decode()

    assert "Authorization" not in content
    assert "query" not in content
    assert "贵州茅台" not in content
