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
    public_response_shape,
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


def _public_diagnostic_payload(
    binding: DirectBinding,
    run_key: str,
    document: object,
    raw_digest: str | None,
    error_types: tuple[str, ...],
) -> bytes:
    return (
        json.dumps(
            {
                "binding_id": binding.binding_id,
                "run_key": run_key,
                "provider_id": binding.provider_id,
                "access_path_id": binding.access_path_id,
                "transport": binding.transport,
                "raw_digest": raw_digest,
                "response_shape": public_response_shape(document, depth=8),
                "error_types": list(error_types),
                "redaction_status": "structure_only",
                "github_run_id": os.environ.get("GITHUB_RUN_ID"),
                "github_sha": os.environ.get("GITHUB_SHA"),
            },
            sort_keys=True,
        )
        + "\n"
    ).encode()


def _error_types(error: BaseException) -> tuple[str, ...]:
    if isinstance(error, BaseExceptionGroup):
        return tuple(
            sorted(
                {
                    nested
                    for child in error.exceptions
                    for nested in _error_types(child)
                }
            )
        )
    return (type(error).__name__,)


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
    public_store = PublicArtifactStore(public_root)
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

    try:
        adapter_result, document, latency_ms, cost_credits = asyncio.run(run())
    except Exception as exc:
        public_store.persist(
            f"{binding.binding_id}-round-{round_value}-diagnostic",
            _public_diagnostic_payload(
                binding,
                cell.run_key,
                None,
                None,
                _error_types(exc),
            ),
        )
        raise
    public_store.persist(
        f"{binding.binding_id}-round-{round_value}-diagnostic",
        _public_diagnostic_payload(
            binding,
            cell.run_key,
            document,
            adapter_result.raw_digest,
            (),
        ),
    )
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
    public = public_store.persist(
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


def test_ac8_public_diagnostic_exposes_only_response_shape() -> None:
    binding = next(
        item
        for item in load_direct_binding_registry(REGISTRY_PATH).bindings
        if item.binding_id == "ifind-cn-600519-dividends"
    )
    content = _public_diagnostic_payload(
        binding,
        "run-key",
        {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(
                        {
                            "code": 1,
                            "data": {"rows": [{"symbol": "600519.SH"}]},
                        }
                    ),
                }
            ]
        },
        "sha256:" + "a" * 64,
        (),
    ).decode()

    assert "response_shape" in content
    assert "rows" in content
    assert "600519.SH" not in content
    assert "Authorization" not in content
    assert "贵州茅台" not in content


def test_ac8_public_transport_failure_exposes_only_exception_types() -> None:
    binding = load_direct_binding_registry(REGISTRY_PATH).bindings[0]
    content = _public_diagnostic_payload(
        binding,
        "run-key",
        None,
        None,
        ("ReadTimeout",),
    ).decode()

    assert '"error_types": ["ReadTimeout"]' in content
    assert "private timeout message" not in content
