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
