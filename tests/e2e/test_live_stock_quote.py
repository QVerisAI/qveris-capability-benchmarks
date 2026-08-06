import asyncio
import json
import os
from pathlib import Path

import httpx
import pytest

from qveris_bench.evidence.store import RawArtifactStore
from qveris_bench.execution.qveris import QverisToolClient, execute_discovered_tool
from qveris_bench.execution.qveris_binding import (
    QverisDirectBinding,
    load_registered_qveris_direct_binding,
    validate_qveris_direct_binding,
)
from qveris_bench.outcomes.extractor import ExtractionError, extract_observation
from qveris_bench.outcomes.stock_quote import (
    StockQuoteExtractionError,
    extract_finnhub_stock_quote,
)

ROOT = Path(__file__).resolve().parents[2]
_FINNHUB_DISCOVERY_DIGEST = (
    "sha256:af842f5deb1cf26f6954a75d322daa7045343f166a387e49732d79c6c3c7f126"
)
_EXPECTED_BINDINGS = {
    "finnhub-aapl-quote": {
        "discovery_digest": _FINNHUB_DISCOVERY_DIGEST,
        "discovery_query": "US stock quote AAPL price timestamp direct provider",
        "tool_id": "finnhub.quote.retrieve.v1.f72cf5ef",
        "parameters": {"symbol": "AAPL"},
    },
    "finnhub-invalid-stock": {
        "discovery_digest": _FINNHUB_DISCOVERY_DIGEST,
        "discovery_query": "US stock quote AAPL price timestamp direct provider",
        "tool_id": "finnhub.quote.retrieve.v1.f72cf5ef",
        "parameters": {"symbol": "NOTASTOCK"},
    },
}


def _validate_fixed_binding(binding: QverisDirectBinding) -> None:
    expected = _EXPECTED_BINDINGS.get(binding.binding_id)
    if expected is None:
        raise AssertionError("live Stock Quote binding is not allowlisted")
    if (
        binding.discovery_digest != expected["discovery_digest"]
        or binding.discovery_query != expected["discovery_query"]
        or binding.tool_id != expected["tool_id"]
        or binding.parameters != expected["parameters"]
    ):
        raise AssertionError("live Stock Quote binding does not match frozen contract")


def _safe_response_failure_reason(
    error: StockQuoteExtractionError, *, negative_control: bool
) -> str:
    if negative_control:
        return "invalid_negative_response"
    message = str(error)
    if "timestamp" in message:
        return "invalid_timestamp"
    if "price" in message:
        return "invalid_price"
    return "unrecognized_provider_response"


def _safe_observation_failure_reason(error: ExtractionError) -> str | None:
    message = str(error)
    if "stale observation field: timestamp" in message:
        return "stale_timestamp"
    if "future observation field: timestamp" in message:
        return "future_timestamp"
    return None


@pytest.mark.skipif(
    os.environ.get("RUN_LIVE_STOCK_QUOTE") != "1",
    reason="live stock quote run is disabled",
)
def test_ac_live_finnhub_direct_quote_positive_and_negative(tmp_path: Path) -> None:
    api_key = os.environ.get("QVERIS_API_KEY")
    if not api_key:
        pytest.skip("QVERIS_API_KEY is required for the live stock quote run")

    async def run() -> None:
        client = QverisToolClient(
            httpx.AsyncClient(), RawArtifactStore(tmp_path, ROOT), api_key
        )
        try:
            for binding_id, negative_control in (
                ("finnhub-aapl-quote", False),
                ("finnhub-invalid-stock", True),
            ):
                binding = load_registered_qveris_direct_binding(
                    ROOT / "cap_packs/qveris-direct-bindings.json", binding_id
                )
                validate_qveris_direct_binding(
                    binding,
                    ROOT / "cap_packs/stock_quote/suite.yaml",
                    ROOT / "providers",
                )
                assert binding.suite_id == "stock-quote-v1"
                assert binding.access_path_id == "finnhub-stock-quote"
                assert binding.provider_id == "finnhub"
                _validate_fixed_binding(binding)
                result = await execute_discovered_tool(
                    client,
                    f"{binding_id}-search",
                    binding.discovery_query,
                    binding.tool_id,
                    binding.parameters,
                )
                document = json.loads(
                    result.result.raw_path.read_text(encoding="utf-8")
                )
                try:
                    facts = extract_finnhub_stock_quote(
                        document,
                        str(binding.parameters["symbol"]),
                        negative_control=negative_control,
                    )
                    observation = extract_observation(
                        ROOT / "cap_packs/stock_quote/observation-schema.yaml",
                        facts,
                        result.result.raw_digest,
                        "1.0.0",
                        negative_control=negative_control,
                    )
                except StockQuoteExtractionError as exc:
                    control = "negative" if negative_control else "positive"
                    reason = _safe_response_failure_reason(
                        exc, negative_control=negative_control
                    )
                    raise AssertionError(
                        f"live Finnhub {control} response failed "
                        f"Stock Quote CAP: {reason}"
                    ) from None
                except ExtractionError as exc:
                    observation_reason = _safe_observation_failure_reason(exc)
                    if observation_reason is None:
                        raise AssertionError(
                            "local Stock Quote observation contract failed"
                        ) from None
                    control = "negative" if negative_control else "positive"
                    raise AssertionError(
                        f"live Finnhub {control} response failed "
                        f"Stock Quote CAP: {observation_reason}"
                    ) from None
                assert observation.facts
        finally:
            await client.close()

    asyncio.run(run())


def test_ac_live_stock_quote_rejects_redirected_binding_before_execution() -> None:
    binding = load_registered_qveris_direct_binding(
        ROOT / "cap_packs/qveris-direct-bindings.json", "finnhub-aapl-quote"
    )
    redirected = binding.model_copy(update={"tool_id": "other.provider.quote"})

    with pytest.raises(AssertionError, match="frozen contract"):
        _validate_fixed_binding(redirected)

    redirected_query = binding.model_copy(update={"discovery_query": "other query"})
    with pytest.raises(AssertionError, match="frozen contract"):
        _validate_fixed_binding(redirected_query)


@pytest.mark.parametrize(
    ("error", "negative_control", "expected"),
    (
        (StockQuoteExtractionError("price is invalid"), False, "invalid_price"),
        (StockQuoteExtractionError("timestamp is invalid"), False, "invalid_timestamp"),
        (
            StockQuoteExtractionError("response must be an object"),
            False,
            "unrecognized_provider_response",
        ),
        (
            StockQuoteExtractionError("negative control lacks an unavailable quote"),
            True,
            "invalid_negative_response",
        ),
    ),
)
def test_ac_live_stock_quote_uses_value_free_response_categories(
    error: StockQuoteExtractionError, negative_control: bool, expected: str
) -> None:
    actual = _safe_response_failure_reason(error, negative_control=negative_control)
    assert actual == expected


@pytest.mark.parametrize(
    ("error", "expected"),
    (
        (ExtractionError("stale observation field: timestamp"), "stale_timestamp"),
        (ExtractionError("future observation field: timestamp"), "future_timestamp"),
        (ExtractionError("observation provenance is invalid"), None),
    ),
)
def test_ac_live_stock_quote_separates_local_observation_errors(
    error: ExtractionError, expected: str | None
) -> None:
    assert _safe_observation_failure_reason(error) == expected
