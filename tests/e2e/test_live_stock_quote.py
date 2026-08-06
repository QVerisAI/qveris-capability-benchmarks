import asyncio
import json
import os
from pathlib import Path

import httpx
import pytest

from qveris_bench.evidence.store import RawArtifactStore
from qveris_bench.execution.qveris import QverisToolClient, execute_discovered_tool
from qveris_bench.execution.qveris_binding import (
    load_registered_qveris_direct_binding,
    validate_qveris_direct_binding,
)
from qveris_bench.outcomes.extractor import ExtractionError, extract_observation
from qveris_bench.outcomes.stock_quote import (
    StockQuoteExtractionError,
    extract_finnhub_stock_quote,
)

ROOT = Path(__file__).resolve().parents[2]


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
                except (StockQuoteExtractionError, ExtractionError):
                    control = "negative" if negative_control else "positive"
                    raise AssertionError(
                        f"live Finnhub {control} response did not satisfy "
                        "Stock Quote CAP"
                    ) from None
                assert observation.facts
        finally:
            await client.close()

    asyncio.run(run())
