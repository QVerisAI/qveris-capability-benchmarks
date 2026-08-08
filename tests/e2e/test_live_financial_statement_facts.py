from __future__ import annotations

import asyncio
import json
import os
from dataclasses import dataclass
from pathlib import Path

import httpx
import pytest

from qveris_bench.cap_packs.financial_statement_facts.extractors import (
    FinancialStatementExtractionError,
    extract_alpha_vantage_income_statement,
    extract_fmp_income_statement,
    extract_sec_company_facts,
)
from qveris_bench.evidence.hashing import sha256_digest
from qveris_bench.evidence.store import PublicArtifactStore, RawArtifactStore
from qveris_bench.execution.qveris import (
    QverisToolClient,
    execute_discovered_tool,
    gateway_metrics,
    public_response_shape,
)
from qveris_bench.execution.qveris_binding import (
    QverisDirectBinding,
    load_registered_qveris_direct_binding,
    validate_qveris_direct_binding,
)
from qveris_bench.outcomes.attribution import classify_provider_negative_reason
from qveris_bench.outcomes.extractor import ExtractionError, extract_observation
from qveris_bench.suites.compiler import compile_suite

ROOT = Path(__file__).resolve().parents[2]
PACK = ROOT / "cap_packs/financial_statement_facts"
BINDINGS_REGISTRY = ROOT / "cap_packs/qveris-direct-bindings-financial-statements.json"
# (access_path_id, provider_id, tool_id, parameters, discovery_digest,
#  discovery_query, negative, case_id)
FAMILY_BINDINGS: dict[
    str, tuple[str, str, str, dict[str, object], str, str, bool, str]
] = {
    "fmp-income-statement-aapl-revenue": (
        "fmp-income-statement",
        "financial-modeling-prep",
        "financialmodelingprep.stable.incomestatement.retrieve.v1.dd6d583f",
        {"symbol": "AAPL", "limit": 5},
        "sha256:74f33b98fc38bd64ab1003d06f574b014e35ec72e233a659e03115f181bbdab4",
        "FMP income statement AAPL annual revenue direct provider",
        False,
        "aapl-revenue-fy2025",
    ),
    "fmp-income-statement-invalid-period": (
        "fmp-income-statement",
        "financial-modeling-prep",
        "financialmodelingprep.stable.incomestatement.retrieve.v1.dd6d583f",
        {"symbol": "AAPL", "limit": 5},
        "sha256:74f33b98fc38bd64ab1003d06f574b014e35ec72e233a659e03115f181bbdab4",
        "FMP income statement AAPL annual revenue direct provider",
        True,
        "invalid-period",
    ),
    "fmp-income-statement-cn-600519-market-coverage": (
        "fmp-income-statement",
        "financial-modeling-prep",
        "financialmodelingprep.stable.incomestatement.retrieve.v1.dd6d583f",
        {"symbol": "600519.SS", "limit": 10},
        "sha256:d96609ce27d279b9994a995f9b028836da1c6f4d904f9359b03a25bf454532a0",
        (
            "FMP as reported income statement 600519.SS Shanghai stock annual "
            "revenue direct provider"
        ),
        False,
        "cn-600519-market-coverage",
    ),
    "fmp-income-statement-aapl-canonical-identifier": (
        "fmp-income-statement",
        "financial-modeling-prep",
        "financialmodelingprep.stable.incomestatement.retrieve.v1.dd6d583f",
        {"symbol": "AAPL", "limit": 5},
        "sha256:74f33b98fc38bd64ab1003d06f574b014e35ec72e233a659e03115f181bbdab4",
        "FMP income statement AAPL annual revenue direct provider",
        False,
        "aapl-canonical-identifier",
    ),
    "fmp-income-statement-aapl-fiscal-period-shape": (
        "fmp-income-statement",
        "financial-modeling-prep",
        "financialmodelingprep.stable.incomestatement.retrieve.v1.dd6d583f",
        {"symbol": "AAPL", "limit": 5},
        "sha256:74f33b98fc38bd64ab1003d06f574b014e35ec72e233a659e03115f181bbdab4",
        "FMP income statement AAPL annual revenue direct provider",
        False,
        "aapl-fiscal-period-shape",
    ),
    "fmp-income-statement-aapl-agent-contract": (
        "fmp-income-statement",
        "financial-modeling-prep",
        "financialmodelingprep.stable.incomestatement.retrieve.v1.dd6d583f",
        {"symbol": "AAPL", "limit": 5},
        "sha256:74f33b98fc38bd64ab1003d06f574b014e35ec72e233a659e03115f181bbdab4",
        "FMP income statement AAPL annual revenue direct provider",
        False,
        "aapl-agent-contract",
    ),
}


@dataclass(frozen=True)
class TerminalEvidence:
    binding_id: str
    run_key: str
    raw_digest: str
    public_digest: str
    outcome: str


def _binding_digest(binding: QverisDirectBinding) -> str:
    return sha256_digest(
        json.dumps(
            binding.model_dump(mode="json"), sort_keys=True, separators=(",", ":")
        ).encode()
    )


def _validate_fixed_binding(
    binding_id: str, binding: QverisDirectBinding
) -> tuple[bool, str, str]:
    expected = FAMILY_BINDINGS.get(binding_id)
    if expected is None:
        raise AssertionError("live Financial Statement binding is not allowlisted")
    if (
        binding.suite_id != "financial-statements-v1"
        or binding.access_path_id != expected[0]
        or binding.provider_id != expected[1]
        or binding.tool_id != expected[2]
        or binding.parameters != expected[3]
        or binding.discovery_digest != expected[4]
        or binding.discovery_query != expected[5]
    ):
        raise AssertionError(
            "live Financial Statement binding does not match frozen contract"
        )
    return expected[6], expected[1], expected[7]


def _selected_run_key(
    compiled: object, binding: QverisDirectBinding, case_id: str, round_number: str
) -> str:
    matches = [
        cell
        for cell in compiled.run_plan.cells
        if cell.case_id == case_id
        and cell.access_path_id == binding.access_path_id
        and cell.round == int(round_number)
    ]
    if len(matches) != 1:
        raise AssertionError(
            "matrix binding must resolve to exactly one frozen RunCell"
        )
    return matches[0].run_key


def _semantic_reason(provider_id: str, case_id: str, document: object) -> str | None:
    negative = case_id == "invalid-period"
    symbol = "600519.SH" if case_id == "cn-600519-market-coverage" else "AAPL"
    fiscal_year = (
        1900 if negative else (2020 if case_id == "cn-600519-market-coverage" else 2025)
    )
    extractors = {
        "financial-modeling-prep": extract_fmp_income_statement,
        "alpha-vantage": extract_alpha_vantage_income_statement,
        "sec-gov": extract_sec_company_facts,
    }
    try:
        facts = extractors[provider_id](
            document,
            symbol,
            fiscal_year,
            negative_control=negative,
            case_id=case_id,
        )
        extract_observation(
            PACK / "observation-schema.yaml",
            facts,
            "sha256:" + "a" * 64,
            "1.0.0",
            negative_control=negative,
        )
    except FinancialStatementExtractionError as exc:
        message = str(exc)
        if negative:
            raise AssertionError(
                "Direct negative response violates its contract"
            ) from exc
        if "unavailable" in message:
            return "fiscal_year_unavailable"
        if "revenue" in message:
            return "invalid_revenue"
        raise AssertionError("Direct positive response violates its contract") from exc
    except ExtractionError as exc:
        raise AssertionError("local observation contract failed") from exc
    return None


def _persist_terminal_evidence(
    root: Path,
    binding_id: str,
    run_key: str,
    raw_digest: str,
    reason: str | None,
    suite_fingerprint: str,
    binding: QverisDirectBinding,
    binding_registry_digest: str,
    latency_ms: float | None,
    cost_credits: float | None,
) -> TerminalEvidence:
    outcome = "completed" if reason is None else "provider_negative"
    attribution = (
        classify_provider_negative_reason(reason) if reason is not None else None
    )
    if reason is not None and attribution is None:
        raise AssertionError(
            f"benchmark-side failure cannot be published as provider_negative: {reason}"
        )
    content = (
        json.dumps(
            {
                "binding_id": binding_id,
                "run_key": run_key,
                "outcome": outcome,
                "raw_digest": raw_digest,
                "binding_digest": _binding_digest(binding),
                "binding_registry_digest": binding_registry_digest,
                "github_run_id": os.environ.get("GITHUB_RUN_ID"),
                "github_sha": os.environ.get("GITHUB_SHA"),
                "reason": reason,
                "failure_attribution": attribution.value if attribution else None,
                "extractor_version": "1.0.0",
                "suite_fingerprint": suite_fingerprint,
                "redaction_status": "sanitized",
                "disclosure_level": "sanitized_public",
                "license_status": "cleared",
                "latency_ms": latency_ms,
                "cost_credits": cost_credits,
            },
            sort_keys=True,
        )
        + "\n"
    ).encode()
    artifact = PublicArtifactStore(root).persist(binding_id, content)
    return TerminalEvidence(binding_id, run_key, raw_digest, artifact.digest, outcome)


@pytest.mark.skipif(
    os.environ.get("RUN_LIVE_FINANCIAL_STATEMENT_FACTS") != "1",
    reason="live financial statement facts run is disabled",
)
def test_ac_live_financial_statement_facts_direct_produces_terminal_evidence(
    tmp_path: Path,
) -> None:
    api_key = os.environ.get("QVERIS_API_KEY")
    binding_id = os.environ.get("FSF_BINDING_ID")
    round_number = os.environ.get("FSF_ROUND")
    if not api_key or not binding_id or not round_number:
        pytest.skip("live Financial Statement environment is incomplete")
    public_root = Path(os.environ.get("LIVE_PUBLIC_EVIDENCE_ROOT", tmp_path / "public"))
    compiled = compile_suite(
        PACK / "suite.yaml", PACK / "cases.yaml", ROOT / "providers"
    )
    binding = load_registered_qveris_direct_binding(BINDINGS_REGISTRY, binding_id)
    binding_registry_digest = sha256_digest(BINDINGS_REGISTRY.read_bytes())
    validate_qveris_direct_binding(binding, PACK / "suite.yaml", ROOT / "providers")
    negative, provider_id, case_id = _validate_fixed_binding(binding_id, binding)
    assert not negative or case_id == "invalid-period"
    run_key = _selected_run_key(compiled, binding, case_id, round_number)

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
            latency_ms, cost_credits = gateway_metrics(document)
            if os.environ.get("FSF_PROBE") == "1":
                probe = (
                    json.dumps(
                        {
                            "binding_id": binding_id,
                            "run_key": run_key,
                            "tool_id": binding.tool_id,
                            "parameters": binding.parameters,
                            "raw_digest": result.result.raw_digest,
                            "response_shape": public_response_shape(document, depth=4),
                        },
                        sort_keys=True,
                    )
                    + "\n"
                ).encode()
                probe_artifact = PublicArtifactStore(public_root).persist(
                    f"{binding_id}-probe", probe
                )
                assert probe_artifact.digest.startswith("sha256:")
                return TerminalEvidence(
                    binding_id,
                    run_key,
                    result.result.raw_digest,
                    probe_artifact.digest,
                    "probe",
                )
            return _persist_terminal_evidence(
                public_root,
                binding_id,
                run_key,
                result.result.raw_digest,
                _semantic_reason(provider_id, case_id, document),
                compiled.fingerprint,
                binding,
                binding_registry_digest,
                latency_ms,
                cost_credits,
            )
        finally:
            await client.close()

    evidence = asyncio.run(run())
    assert evidence.public_digest != evidence.raw_digest


def test_ac_live_financial_statement_facts_rejects_redirected_binding() -> None:
    binding = load_registered_qveris_direct_binding(
        BINDINGS_REGISTRY, "fmp-income-statement-aapl-revenue"
    )
    with pytest.raises(AssertionError, match="frozen contract"):
        _validate_fixed_binding(
            "fmp-income-statement-aapl-revenue",
            binding.model_copy(update={"tool_id": "other.provider.tool"}),
        )
    with pytest.raises(AssertionError, match="frozen contract"):
        _validate_fixed_binding(
            "fmp-income-statement-aapl-revenue",
            binding.model_copy(update={"discovery_digest": "sha256:" + "0" * 64}),
        )


def test_ac_live_financial_statement_facts_rejects_malformed_response() -> None:
    with pytest.raises(AssertionError, match="positive response violates"):
        _semantic_reason("financial-modeling-prep", "aapl-revenue-fy2025", {})
    with pytest.raises(AssertionError, match="negative response violates"):
        _semantic_reason("financial-modeling-prep", "invalid-period", {})
