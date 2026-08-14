from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

import httpx
import pytest

from qveris_bench.cap_packs.govt_bond_yield.direct import (
    GovernmentBondDirectResult,
    evaluate_government_bond_document,
)
from qveris_bench.cap_packs.govt_bond_yield.models import (
    GovernmentBondRequestIdentity,
    validate_government_bond_request_identities,
)
from qveris_bench.evidence.store import PublicArtifactStore, RawArtifactStore
from qveris_bench.execution.direct_binding import (
    DirectBinding,
    direct_binding_registry_digest,
    load_direct_binding_registry,
    validate_direct_binding_registry,
)
from qveris_bench.execution.qveris import (
    QverisDirectExecution,
    QverisToolClient,
    execute_discovered_tool,
    gateway_metrics,
)
from qveris_bench.models.enums import CellState, FailureAttribution
from qveris_bench.suites.compiler import compile_suite

ROOT = Path(__file__).resolve().parents[2]
PACK = ROOT / "cap_packs/govt-bond-yield"


def _inputs() -> tuple[Path, Path, Path]:
    prefix = os.environ.get("GOVT_BOND_YIELD_SUITE", "baseline")
    if prefix not in {"baseline", "market"}:
        raise AssertionError("unknown government-bond-yield suite")
    return (
        PACK / ("suite.yaml" if prefix == "baseline" else "market-suite.yaml"),
        PACK / ("cases.yaml" if prefix == "baseline" else "market-cases.yaml"),
        PACK
        / (
            "direct-bindings.json"
            if prefix == "baseline"
            else "market-direct-bindings.json"
        ),
    )


def _public_terminal(
    binding: DirectBinding,
    run_key: str,
    raw_digest: str,
    result: GovernmentBondDirectResult,
    suite_fingerprint: str,
    registry_digest: str,
    latency_ms: float | None,
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
                "github_run_id": os.environ.get("GITHUB_RUN_ID"),
                "github_sha": os.environ.get("GITHUB_SHA"),
            },
            sort_keys=True,
        )
        + "\n"
    ).encode()


@pytest.mark.skipif(
    os.environ.get("RUN_LIVE_GOVT_BOND_YIELD") != "1",
    reason="live government-bond-yield run is disabled",
)
def test_live_government_bond_cell_produces_sanitized_terminal(
    tmp_path: Path,
) -> None:
    binding_id = os.environ.get("GOVT_BOND_YIELD_BINDING_ID")
    round_value = os.environ.get("GOVT_BOND_YIELD_ROUND")
    if not binding_id or not round_value:
        pytest.skip("live government-bond-yield matrix environment is incomplete")
    suite_path, cases_path, registry_path = _inputs()
    registry = load_direct_binding_registry(registry_path)
    validate_direct_binding_registry(
        registry,
        suite_path,
        cases_path,
        ROOT / "providers",
        cap_path=PACK / "cap.yaml",
    )
    compiled = compile_suite(
        suite_path, cases_path, ROOT / "providers", PACK / "cap.yaml"
    )
    validate_government_bond_request_identities(registry, compiled)
    binding = next(item for item in registry.bindings if item.binding_id == binding_id)
    cell = next(
        item
        for item in compiled.run_plan.cells
        if item.case_id == binding.case_id
        and item.access_path_id == binding.access_path_id
        and item.round == int(round_value)
        and item.applicable
    )
    case = next(item for item in compiled.cases if item.case_id == binding.case_id)
    api_key = os.environ.get("QVERIS_API_KEY")
    if not api_key:
        pytest.skip("QVERIS_API_KEY is required")
    raw_store = RawArtifactStore(
        Path(os.environ.get("LIVE_RAW_EVIDENCE_ROOT", tmp_path / "raw")), ROOT
    )

    async def run() -> QverisDirectExecution:
        client = QverisToolClient(httpx.AsyncClient(), raw_store, api_key)
        try:
            return await execute_discovered_tool(
                client,
                f"{binding.binding_id}-round-{round_value}-search",
                str(binding.discovery_query),
                binding.tool_id,
                binding.parameters,
                capture_execute_http_error=True,
            )
        finally:
            await client.close()

    execution = asyncio.run(run())
    raw_bytes = execution.result.raw_path.read_bytes()
    try:
        document = json.loads(raw_bytes)
    except json.JSONDecodeError:
        document = None
    if execution.result.status_code >= 400:
        payload = {"status_code": execution.result.status_code, "data": document}
    elif isinstance(document, dict) and isinstance(document.get("result"), dict):
        payload = document["result"]
    else:
        payload = {"status_code": 520, "data": {"protocol_error": "invalid result"}}
    if execution.envelope_digest is None or execution.envelope_path is None:
        raise AssertionError("QVeris execution envelope is missing")
    latency_ms, _ = (
        gateway_metrics(document) if isinstance(document, dict) else (None, None)
    )
    result = evaluate_government_bond_document(
        str(binding.provider_id),
        payload,
        case,
        request_identity=GovernmentBondRequestIdentity.model_validate(
            binding.request_identity
        ),
    )
    public_store = PublicArtifactStore(
        Path(os.environ.get("LIVE_PUBLIC_EVIDENCE_ROOT", tmp_path / "public"))
    )
    public = public_store.persist(
        f"{binding.binding_id}-round-{round_value}",
        _public_terminal(
            binding,
            cell.run_key,
            execution.envelope_digest,
            result,
            compiled.fingerprint,
            direct_binding_registry_digest(registry_path),
            latency_ms,
        ),
    )
    assert public.digest != execution.envelope_digest
    assert result.state in {
        CellState.COMPLETED,
        CellState.PROVIDER_NEGATIVE,
        CellState.INFRA_BLOCKED,
    }


def test_public_terminal_excludes_parameters_credentials_and_account_costs() -> None:
    binding = load_direct_binding_registry(PACK / "direct-bindings.json").bindings[0]
    content = _public_terminal(
        binding,
        "run-key",
        "sha256:" + "a" * 64,
        GovernmentBondDirectResult(
            CellState.INFRA_BLOCKED,
            {"execution_failure": "rate_limited"},
            ("symbol",),
            FailureAttribution.RATE_LIMITED,
        ),
        "b" * 64,
        "sha256:" + "c" * 64,
        1.0,
    ).decode()
    assert "Authorization" not in content
    assert '"parameters"' not in content
    assert '"cost_credits"' not in content
