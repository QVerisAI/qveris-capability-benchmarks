import asyncio
import json
import os
from dataclasses import dataclass
from pathlib import Path

import httpx
import pytest

from qveris_bench.cap_packs.stock_quote_smoke.extractors import (
    StockQuoteExtractionError,
    extract_eodhd_stock_quote,
    extract_finnhub_stock_quote,
)
from qveris_bench.evidence.store import PublicArtifactStore, RawArtifactStore
from qveris_bench.execution.qveris import QverisToolClient, execute_discovered_tool
from qveris_bench.execution.qveris_binding import (
    QverisDirectBinding,
    load_registered_qveris_direct_binding,
    validate_qveris_direct_binding,
)
from qveris_bench.outcomes.extractor import ExtractionError, extract_observation
from qveris_bench.suites.compiler import compile_suite

ROOT = Path(__file__).resolve().parents[2]
PACK = ROOT / "cap_packs/stock_quote_smoke_v2"
_EXPECTED = {
    "finnhub-aapl-quote": (
        "finnhub-stock-quote",
        "finnhub",
        "finnhub.quote.retrieve.v1.f72cf5ef",
        {"symbol": "AAPL"},
        False,
        "aapl-quote",
    ),
    "finnhub-invalid-stock": (
        "finnhub-stock-quote",
        "finnhub",
        "finnhub.quote.retrieve.v1.f72cf5ef",
        {"symbol": "NOTASTOCK"},
        True,
        "invalid-stock",
    ),
    "eodhd-aapl-quote": (
        "eodhd-stock-quote",
        "eodhd",
        "eodhd.live_v2.us_quote_delayed.retrieve.v1.f0e13d45",
        {"s": "AAPL.US", "page[limit]": 1},
        False,
        "aapl-quote",
    ),
    "eodhd-invalid-stock": (
        "eodhd-stock-quote",
        "eodhd",
        "eodhd.live_v2.us_quote_delayed.retrieve.v1.f0e13d45",
        {"s": "NOTASTOCK.US", "page[limit]": 1},
        True,
        "invalid-stock",
    ),
}


@dataclass(frozen=True)
class TerminalEvidence:
    binding_id: str
    run_key: str
    raw_digest: str
    public_digest: str
    outcome: str


def _validate_fixed_binding(
    binding_id: str, binding: QverisDirectBinding
) -> tuple[bool, str, str]:
    expected = _EXPECTED.get(binding_id)
    if expected is None:
        raise AssertionError("live Stock Quote v2 binding is not allowlisted")
    if (
        binding.suite_id != "stock-quote-v2"
        or binding.access_path_id != expected[0]
        or binding.provider_id != expected[1]
        or binding.tool_id != expected[2]
        or binding.parameters != expected[3]
    ):
        raise AssertionError(
            "live Stock Quote v2 binding does not match frozen contract"
        )
    return expected[4], expected[1], expected[5]


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


def _semantic_reason(provider_id: str, document: object, negative: bool) -> str | None:
    try:
        extractor = (
            extract_finnhub_stock_quote
            if provider_id == "finnhub"
            else extract_eodhd_stock_quote
        )
        facts = extractor(
            document, "AAPL" if not negative else "NOTASTOCK", negative_control=negative
        )
        extract_observation(
            PACK / "observation-schema.yaml",
            facts,
            "sha256:" + "a" * 64,
            "1.0.0",
            negative_control=negative,
        )
    except StockQuoteExtractionError as exc:
        message = str(exc)
        if "validation" in message or "unavailable" in message:
            return "invalid_negative_response"
        if "timestamp" in message:
            return "invalid_timestamp"
        if "price" in message:
            return "invalid_price"
        return "unrecognized_provider_response"
    except ExtractionError as exc:
        if "stale" in str(exc):
            return "stale_timestamp"
        if "future" in str(exc):
            return "future_timestamp"
        raise AssertionError("local observation contract failed") from None
    return None


def _persist_terminal_evidence(
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
        )
        + "\n"
    ).encode()
    artifact = PublicArtifactStore(root).persist(binding_id, content)
    return TerminalEvidence(binding_id, run_key, raw_digest, artifact.digest, outcome)


@pytest.mark.skipif(
    os.environ.get("RUN_LIVE_STOCK_QUOTE_V2") != "1",
    reason="live stock quote v2 run is disabled",
)
def test_ac_live_stock_quote_v2_direct_produces_terminal_evidence(
    tmp_path: Path,
) -> None:
    api_key = os.environ.get("QVERIS_API_KEY")
    binding_id = os.environ.get("STOCK_QUOTE_V2_BINDING_ID")
    round_number = os.environ.get("STOCK_QUOTE_V2_ROUND")
    if not api_key or not binding_id or not round_number:
        pytest.skip("live Stock Quote v2 environment is incomplete")
    public_root = Path(os.environ.get("LIVE_PUBLIC_EVIDENCE_ROOT", tmp_path / "public"))
    compiled = compile_suite(
        PACK / "suite.yaml", PACK / "cases.yaml", ROOT / "providers"
    )
    binding = load_registered_qveris_direct_binding(
        ROOT / "cap_packs/qveris-direct-bindings.json", binding_id
    )
    validate_qveris_direct_binding(binding, PACK / "suite.yaml", ROOT / "providers")
    negative, provider_id, case_id = _validate_fixed_binding(binding_id, binding)
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
            return _persist_terminal_evidence(
                public_root,
                binding_id,
                run_key,
                result.result.raw_digest,
                _semantic_reason(provider_id, document, negative),
                compiled.fingerprint,
            )
        finally:
            await client.close()

    evidence = asyncio.run(run())
    assert evidence.public_digest != evidence.raw_digest


def test_ac_live_stock_quote_v2_rejects_redirected_binding_before_execution() -> None:
    binding = load_registered_qveris_direct_binding(
        ROOT / "cap_packs/qveris-direct-bindings.json", "eodhd-aapl-quote"
    )
    with pytest.raises(AssertionError, match="frozen contract"):
        _validate_fixed_binding(
            "eodhd-aapl-quote",
            binding.model_copy(update={"tool_id": "other.provider.tool"}),
        )
