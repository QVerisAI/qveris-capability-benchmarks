from qveris_bench.cap_packs.corporate_actions.direct import evaluate
from qveris_bench.models.enums import CellState, FailureAttribution


def test_positive_responses_extract_only_the_cap_contract() -> None:
    payloads = {
        "eodhd": {"status_code": 200, "data": 'Date,"Stock Splits"\n2020-08-31,4/1\n'},
        "twelve-data": {
            "status_code": 200,
            "data": {"meta": {"symbol": "AAPL"}, "splits": [{"date": "2020-08-31"}]},
        },
        "alpha-vantage": {
            "status_code": 200,
            "data": {"symbol": "AAPL", "data": [{"effective_date": "2020-08-31"}]},
        },
        "massive-stocks": {
            "status_code": 200,
            "data": {"results": [{"ticker": "AAPL", "execution_date": "2020-08-31"}]},
        },
    }
    for provider_id, payload in payloads.items():
        terminal = evaluate(provider_id, "aapl-splits-fixed-window", payload)
        assert terminal.state is CellState.COMPLETED
        assert terminal.facts == {
            "symbol": "AAPL",
            "action_type": "split",
            "date": "2020-08-31",
        }


def test_only_explicit_negative_responses_complete_the_control() -> None:
    eodhd = evaluate(
        "eodhd",
        "invalid-corporate-actions-symbol",
        {"status_code": 404, "data": "Symbol not found"},
    )
    twelve = evaluate(
        "twelve-data",
        "invalid-corporate-actions-symbol",
        {
            "status_code": 4042,
            "data": {"status": "error", "message": "symbol is invalid"},
        },
    )
    alpha = evaluate(
        "alpha-vantage",
        "invalid-corporate-actions-symbol",
        {"status_code": 200, "data": {"symbol": "NOTASTOCK", "data": []}},
    )
    assert eodhd.state is twelve.state is CellState.COMPLETED
    assert eodhd.attribution is FailureAttribution.PROVIDER_VALIDATION_ERROR
    assert alpha.state is CellState.PROVIDER_NEGATIVE
