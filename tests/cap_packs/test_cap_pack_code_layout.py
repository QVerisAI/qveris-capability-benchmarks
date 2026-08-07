from qveris_bench.cap_packs.etf_holdings.extractors import (
    extract_alpha_vantage_etf_holdings,
)
from qveris_bench.cap_packs.stock_quote_smoke.extractors import (
    extract_finnhub_stock_quote,
)


def test_ac_cap_specific_extractors_live_with_their_cap_pack() -> None:
    assert callable(extract_alpha_vantage_etf_holdings)
    assert callable(extract_finnhub_stock_quote)
