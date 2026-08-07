import json
from pathlib import Path

from qveris_bench.suites.compiler import compile_suite
from qveris_bench.suites.loader import load_suite

ROOT = Path(__file__).resolve().parents[2]
PACK = ROOT / "cap_packs" / "stock_quote_smoke_v2"
PROVIDERS = ROOT / "providers"


def test_ac_stock_quote_smoke_v2_freezes_two_direct_providers_for_two_rounds() -> None:
    suite = load_suite(PACK / "suite.yaml")
    compiled = compile_suite(PACK / "suite.yaml", PACK / "cases.yaml", PROVIDERS)

    assert suite.suite_id == "stock-quote-v2"
    assert suite.rounds == 2
    assert suite.access_path_ids == ("finnhub-stock-quote", "eodhd-stock-quote")
    assert len(compiled.run_plan.cells) == 8
    assert {cell.mode.value for cell in compiled.run_plan.cells} == {"direct"}


def test_ac_stock_quote_smoke_v2_binds_eodhd_to_the_json_quote_interface() -> None:
    bindings = json.loads((ROOT / "cap_packs/qveris-direct-bindings.json").read_text())
    by_id = {item["binding_id"]: item for item in bindings["bindings"]}

    assert by_id["eodhd-aapl-quote"]["tool_id"] == (
        "eodhd.live_v2.us_quote_delayed.retrieve.v1.f0e13d45"
    )
    assert by_id["eodhd-aapl-quote"]["parameters"] == {
        "s": "AAPL.US",
        "page[limit]": 1,
    }
    assert by_id["eodhd-invalid-stock"]["parameters"] == {
        "s": "NOTASTOCK.US",
        "page[limit]": 1,
    }
