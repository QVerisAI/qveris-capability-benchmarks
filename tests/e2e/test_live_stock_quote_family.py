from __future__ import annotations

import asyncio
import json
import os
from dataclasses import dataclass
from pathlib import Path

import httpx
import pytest

from qveris_bench.cap_packs.stock_quote_family.extractors import (
    StockQuoteExtractionError,
    extract_eodhd_stock_quote,
    extract_finnhub_stock_quote,
)
from qveris_bench.evidence.hashing import sha256_digest
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
PACK = ROOT / "cap_packs/stock_quote_family"
BINDINGS_REGISTRY = ROOT / "cap_packs/qveris-direct-bindings-stock-quote-family.json"

# (access_path_id, provider_id, tool_id, parameters, discovery_digest,
#  discovery_query, negative, case_id, symbol)
FAMILY_BINDINGS: dict[
    str, tuple[str, str, str, dict[str, object], str, str, bool, str, str]
] = {
    "finnhub-aapl-quote-family": (
        "finnhub-stock-quote",
        "finnhub",
        "finnhub.quote.retrieve.v1.f72cf5ef",
        {"symbol": "AAPL"},
        "sha256:af842f5deb1cf26f6954a75d322daa7045343f166a387e49732d79c6c3c7f126",
        "US stock quote AAPL price timestamp direct provider",
        False,
        "aapl-quote",
        "AAPL",
    ),
    "finnhub-invalid-stock-family": (
        "finnhub-stock-quote",
        "finnhub",
        "finnhub.quote.retrieve.v1.f72cf5ef",
        {"symbol": "NOTASTOCK"},
        "sha256:af842f5deb1cf26f6954a75d322daa7045343f166a387e49732d79c6c3c7f126",
        "US stock quote AAPL price timestamp direct provider",
        True,
        "invalid-stock",
        "NOTASTOCK",
    ),
    "finnhub-aapl-freshness-family": (
        "finnhub-stock-quote",
        "finnhub",
        "finnhub.quote.retrieve.v1.f72cf5ef",
        {"symbol": "AAPL"},
        "sha256:af842f5deb1cf26f6954a75d322daa7045343f166a387e49732d79c6c3c7f126",
        "US stock quote AAPL price timestamp direct provider",
        False,
        "aapl-freshness-precision",
        "AAPL",
    ),
    "finnhub-600519-coverage-family": (
        "finnhub-stock-quote",
        "finnhub",
        "finnhub.quote.retrieve.v1.f72cf5ef",
        {"symbol": "600519.SH"},
        "sha256:af842f5deb1cf26f6954a75d322daa7045343f166a387e49732d79c6c3c7f126",
        "US stock quote AAPL price timestamp direct provider",
        False,
        "cn-600519-market-coverage",
        "600519.SH",
    ),
    "finnhub-600519-agent-family": (
        "finnhub-stock-quote",
        "finnhub",
        "finnhub.quote.retrieve.v1.f72cf5ef",
        {"symbol": "600519.SH"},
        "sha256:af842f5deb1cf26f6954a75d322daa7045343f166a387e49732d79c6c3c7f126",
        "US stock quote AAPL price timestamp direct provider",
        False,
        "cn-600519-agent-contract",
        "600519.SH",
    ),
    "eodhd-aapl-quote-family": (
        "eodhd-stock-quote",
        "eodhd",
        "eodhd.live_v2.us_quote_delayed.retrieve.v1.f0e13d45",
        {"s": "AAPL.US", "page[limit]": 1},
        "sha256:6c30f7b6d4e721afbca0670e3e55468687d6179e42cc60368bc71ee5e0a1952e",
        "EODHD real-time delayed stock quote AAPL price timestamp direct provider",
        False,
        "aapl-quote",
        "AAPL",
    ),
    "eodhd-invalid-stock-family": (
        "eodhd-stock-quote",
        "eodhd",
        "eodhd.live_v2.us_quote_delayed.retrieve.v1.f0e13d45",
        {"s": "NOTASTOCK.US", "page[limit]": 1},
        "sha256:6c30f7b6d4e721afbca0670e3e55468687d6179e42cc60368bc71ee5e0a1952e",
        "EODHD real-time delayed stock quote AAPL price timestamp direct provider",
        True,
        "invalid-stock",
        "NOTASTOCK",
    ),
    "eodhd-aapl-freshness-family": (
        "eodhd-stock-quote",
        "eodhd",
        "eodhd.live_v2.us_quote_delayed.retrieve.v1.f0e13d45",
        {"s": "AAPL.US", "page[limit]": 1},
        "sha256:6c30f7b6d4e721afbca0670e3e55468687d6179e42cc60368bc71ee5e0a1952e",
        "EODHD real-time delayed stock quote AAPL price timestamp direct provider",
        False,
        "aapl-freshness-precision",
        "AAPL",
    ),
    "eodhd-600519-coverage-family": (
        "eodhd-stock-quote",
        "eodhd",
        "eodhd.live_v2.us_quote_delayed.retrieve.v1.f0e13d45",
        {"s": "600519.SH", "page[limit]": 1},
        "sha256:6c30f7b6d4e721afbca0670e3e55468687d6179e42cc60368bc71ee5e0a1952e",
        "EODHD real-time delayed stock quote AAPL price timestamp direct provider",
        False,
        "cn-600519-market-coverage",
        "600519.SH",
    ),
    "eodhd-600519-agent-family": (
        "eodhd-stock-quote",
        "eodhd",
        "eodhd.live_v2.us_quote_delayed.retrieve.v1.f0e13d45",
        {"s": "600519.SH", "page[limit]": 1},
        "sha256:6c30f7b6d4e721afbca0670e3e55468687d6179e42cc60368bc71ee5e0a1952e",
        "EODHD real-time delayed stock quote AAPL price timestamp direct provider",
        False,
        "cn-600519-agent-contract",
        "600519.SH",
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
) -> tuple[bool, str, str, str]:
    expected = FAMILY_BINDINGS.get(binding_id)
    if expected is None:
        raise AssertionError("live Stock Quote family binding is not allowlisted")
    if (
        binding.suite_id != "stock-quote-v3"
        or binding.access_path_id != expected[0]
        or binding.provider_id != expected[1]
        or binding.tool_id != expected[2]
        or binding.parameters != expected[3]
        or binding.discovery_digest != expected[4]
        or binding.discovery_query != expected[5]
    ):
        raise AssertionError(
            "live Stock Quote family binding does not match frozen contract"
        )
    return expected[6], expected[1], expected[7], expected[8]


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
    negative = case_id == "invalid-stock"
    symbol = "NOTASTOCK" if negative else "AAPL"
    if case_id in {"cn-600519-market-coverage", "cn-600519-agent-contract"}:
        symbol = "600519.SH"
    try:
        extractor = (
            extract_finnhub_stock_quote
            if provider_id == "finnhub"
            else extract_eodhd_stock_quote
        )
        facts = extractor(document, symbol, negative_control=negative)
        extract_observation(
            PACK / "observation-schema.yaml",
            facts,
            "sha256:" + "a" * 64,
            "1.0.0",
            negative_control=negative,
        )
    except StockQuoteExtractionError as exc:
        message = str(exc)
        if negative:
            raise AssertionError(
                "Direct negative response violates its contract"
            ) from exc
        if "unavailable" in message:
            return "unavailable_quote"
        if "timestamp" in message:
            return "invalid_timestamp"
        if "price" in message:
            return "invalid_price"
        raise AssertionError("Direct positive response violates its contract") from exc
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
    binding: QverisDirectBinding,
    binding_registry_digest: str,
) -> TerminalEvidence:
    outcome = "completed" if reason is None else "provider_negative"
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
    os.environ.get("RUN_LIVE_STOCK_QUOTE_FAMILY") != "1",
    reason="live stock quote family run is disabled",
)
def test_ac_live_stock_quote_family_direct_produces_terminal_evidence(
    tmp_path: Path,
) -> None:
    api_key = os.environ.get("QVERIS_API_KEY")
    binding_id = os.environ.get("STOCK_QUOTE_FAMILY_BINDING_ID")
    round_number = os.environ.get("STOCK_QUOTE_FAMILY_ROUND")
    if not api_key or not binding_id or not round_number:
        pytest.skip("live Stock Quote family environment is incomplete")
    public_root = Path(os.environ.get("LIVE_PUBLIC_EVIDENCE_ROOT", tmp_path / "public"))
    compiled = compile_suite(
        PACK / "suite.yaml", PACK / "cases.yaml", ROOT / "providers"
    )
    binding = load_registered_qveris_direct_binding(BINDINGS_REGISTRY, binding_id)
    binding_registry_digest = sha256_digest(BINDINGS_REGISTRY.read_bytes())
    validate_qveris_direct_binding(binding, PACK / "suite.yaml", ROOT / "providers")
    negative, provider_id, case_id, symbol = _validate_fixed_binding(
        binding_id, binding
    )
    assert not negative or case_id == "invalid-stock"
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
                _semantic_reason(provider_id, case_id, document),
                compiled.fingerprint,
                binding,
                binding_registry_digest,
            )
        finally:
            await client.close()

    evidence = asyncio.run(run())
    assert evidence.public_digest != evidence.raw_digest


def test_ac_live_stock_quote_family_rejects_redirected_binding_before_execution() -> (
    None
):
    binding = load_registered_qveris_direct_binding(
        BINDINGS_REGISTRY, "eodhd-aapl-quote-family"
    )
    with pytest.raises(AssertionError, match="frozen contract"):
        _validate_fixed_binding(
            "eodhd-aapl-quote-family",
            binding.model_copy(update={"tool_id": "other.provider.tool"}),
        )
    with pytest.raises(AssertionError, match="frozen contract"):
        _validate_fixed_binding(
            "eodhd-aapl-quote-family",
            binding.model_copy(update={"discovery_query": "other query"}),
        )
    with pytest.raises(AssertionError, match="frozen contract"):
        _validate_fixed_binding(
            "eodhd-aapl-quote-family",
            binding.model_copy(update={"discovery_digest": "sha256:" + "0" * 64}),
        )


def test_ac_live_stock_quote_family_rejects_malformed_provider_response() -> None:
    with pytest.raises(AssertionError, match="positive response violates"):
        _semantic_reason("eodhd", "aapl-quote", {})
    with pytest.raises(AssertionError, match="negative response violates"):
        _semantic_reason("eodhd", "invalid-stock", {})
