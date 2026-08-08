import pytest

from qveris_bench.cap_packs.financial_statement_facts.extractors import (
    FinancialStatementExtractionError,
    extract_fmp_income_statement,
)
from qveris_bench.cap_packs.sec_filing_evidence.extractors import (
    SecFilingExtractionError,
    extract_massive_stocks_risk_factors,
)


def _fmp_document() -> dict[str, object]:
    return {
        "result": {
            "data": [
                {
                    "date": "2020-12-31",
                    "revenue": 274515000000,
                    "reportedCurrency": "USD",
                },
                {
                    "date": "2025-09-27",
                    "revenue": 391035000000,
                    "reportedCurrency": "USD",
                },
            ]
        }
    }


def test_ac1_fmp_core_case_facts_are_unchanged() -> None:
    facts = extract_fmp_income_statement(_fmp_document(), "AAPL", 2025)

    assert facts["symbol"] == "AAPL"
    assert facts["revenue"] == 391035000000
    assert facts["currency"] == "USD"


def test_ac1_fmp_coverage_case_adds_market_identity() -> None:
    facts = extract_fmp_income_statement(
        _fmp_document(), "600519.SH", 2020, case_id="cn-600519-market-coverage"
    )

    assert facts["market"] == "CN"
    assert facts["currency"] == "USD"


def test_ac1_fmp_canonical_identifier_case_reports_resolution() -> None:
    facts = extract_fmp_income_statement(
        _fmp_document(), "AAPL", 2025, case_id="aapl-canonical-identifier"
    )

    assert facts["resolved_identifier"] == "AAPL"


def test_ac1_fmp_fiscal_period_shape_case_reports_unit_and_period() -> None:
    facts = extract_fmp_income_statement(
        _fmp_document(), "AAPL", 2025, case_id="aapl-fiscal-period-shape"
    )

    assert facts["unit"] == "USD"
    assert facts["period_label"] == "FY2025"


def test_ac1_fmp_agent_contract_case_keeps_core_facts() -> None:
    facts = extract_fmp_income_statement(
        _fmp_document(), "AAPL", 2025, case_id="aapl-agent-contract"
    )

    assert set(facts) >= {"symbol", "fiscal_year", "revenue", "currency"}


def _massive_document() -> dict[str, object]:
    return {
        "result": {
            "data": {
                "results": [
                    {
                        "ticker": "AAPL",
                        "cik": "0000320193",
                        "filing_date": "2024-11-01",
                        "text": (
                            "our operations depend on a complex and global supply chain"
                        ),
                    }
                ],
                "status": "success",
            }
        }
    }


def test_ac2_massive_envelope_with_result_data_results_is_supported() -> None:
    facts = extract_massive_stocks_risk_factors(_massive_document(), "AAPL")

    assert facts["filing_id"] == "0000320193-2024-11-01"
    assert "supply chain" in facts["evidence"]
    assert facts["citation"].startswith("10-K filed")


def test_ac2_massive_cik_case_reports_resolution() -> None:
    facts = extract_massive_stocks_risk_factors(
        _massive_document(), "AAPL", case_id="cik-canonical-identifier"
    )

    assert facts["resolved_identifier"] == "AAPL"


def test_ac2_massive_missing_results_raise_provider_side_unavailable() -> None:
    with pytest.raises(SecFilingExtractionError, match="risk factors are missing"):
        extract_massive_stocks_risk_factors({"result": {"data": {}}}, "AAPL")


def test_ac1_fmp_missing_fiscal_year_is_not_a_revenue_parse_failure() -> None:
    with pytest.raises(
        FinancialStatementExtractionError, match="fiscal year unavailable"
    ):
        extract_fmp_income_statement(_fmp_document(), "AAPL", 1900)
