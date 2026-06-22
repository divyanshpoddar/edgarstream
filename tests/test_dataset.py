"""
Cross-industry dataset regression tests.

Covers 5 10-K filers across tech/energy/retail/finance + 2 large 13F filers.
All URLs and fixture values validated against live EDGAR on 2026-06-09.
Tests skip gracefully on SEC 503/429 rate-limit responses.
"""
import pytest
from services.parser.form_10k import extract_10k_financials
from services.parser.form_13f import extract_13f_holdings


def _skip_on_rate_limit(fn, *args):
    """Call fn(*args); pytest.skip on 503/429, re-raise everything else."""
    try:
        return fn(*args)
    except Exception as e:
        msg = str(e)
        if "503" in msg or "429" in msg or "Service Unavailable" in msg:
            pytest.skip(f"SEC EDGAR rate limit: {e}")
        raise


# ---------------------------------------------------------------------------
# 10-K fixtures  (values confirmed from EDGAR on 2026-06-09, 1 % tolerance)
# ---------------------------------------------------------------------------

TEN_K_CASES = [
    {
        "id":       "apple_fy2025",
        "company":  "Apple",
        "url":      "https://www.sec.gov/Archives/edgar/data/320193/000032019325000079/0000320193-25-000079-index.htm",
        "assets":   359_241_000_000,
        "revenues": 416_161_000_000,
        "net_income": 112_010_000_000,
    },
    {
        "id":       "microsoft_fy2025",
        "company":  "Microsoft",
        "url":      "https://www.sec.gov/Archives/edgar/data/789019/000095017025100235/0000950170-25-100235-index.htm",
        "assets":   619_003_000_000,
        "revenues": 281_724_000_000,
        "net_income": 101_832_000_000,
    },
    {
        "id":       "exxon_fy2025",
        "company":  "ExxonMobil",
        "url":      "https://www.sec.gov/Archives/edgar/data/34088/000003408826000045/0000034088-26-000045-index.htm",
        "assets":   448_980_000_000,
        "revenues": 332_238_000_000,
        "net_income": 29_764_000_000,
    },
    {
        "id":       "walmart_fy2026",
        "company":  "Walmart",
        "url":      "https://www.sec.gov/Archives/edgar/data/104169/000010416926000055/0000104169-26-000055-index.htm",
        "assets":   284_668_000_000,
        "revenues": 713_163_000_000,
        "net_income": 21_893_000_000,
    },
    {
        "id":       "jpmorgan_fy2025",
        "company":  "JPMorgan Chase",
        "url":      "https://www.sec.gov/Archives/edgar/data/19617/000162828026008131/0001628280-26-008131-index.htm",
        "assets":   4_424_900_000_000,
        "revenues": 182_447_000_000,
        "net_income": 57_048_000_000,
    },
]


@pytest.fixture(scope="module", params=TEN_K_CASES, ids=[c["id"] for c in TEN_K_CASES])
def ten_k_result(request):
    case = request.param
    result = _skip_on_rate_limit(extract_10k_financials, case["url"])
    return case, result


class TestDataset10K:
    """Parametrised 10-K extraction across 5 industries."""

    def test_returns_dict(self, ten_k_result):
        _, result = ten_k_result
        assert isinstance(result, dict)

    def test_assets_nonzero(self, ten_k_result):
        case, result = ten_k_result
        assert result.get("Assets", 0) > 0, f"{case['company']}: Assets is zero"

    def test_revenues_nonzero(self, ten_k_result):
        case, result = ten_k_result
        assert result.get("Revenues", 0) > 0, f"{case['company']}: Revenues is zero"

    def test_assets_within_1pct(self, ten_k_result):
        case, result = ten_k_result
        expected = case["assets"]
        actual   = result.get("Assets", 0)
        assert abs(actual - expected) / expected < 0.01, (
            f"{case['company']}: Assets {actual:,} deviates >1% from {expected:,}"
        )

    def test_revenues_within_1pct(self, ten_k_result):
        case, result = ten_k_result
        expected = case["revenues"]
        actual   = result.get("Revenues", 0)
        assert abs(actual - expected) / expected < 0.01, (
            f"{case['company']}: Revenues {actual:,} deviates >1% from {expected:,}"
        )

    def test_net_income_within_1pct(self, ten_k_result):
        case, result = ten_k_result
        expected = case["net_income"]
        actual   = result.get("NetIncomeLoss", 0)
        # Net income can be negative; use absolute fixture for % check
        assert abs(actual - expected) / abs(expected) < 0.01, (
            f"{case['company']}: NetIncome {actual:,} deviates >1% from {expected:,}"
        )

    def test_balance_sheet_identity(self, ten_k_result):
        case, result = ten_k_result
        assets      = result.get("Assets", 0)
        liabilities = result.get("Liabilities", 0)
        assert assets >= liabilities, (
            f"{case['company']}: Assets {assets:,} < Liabilities {liabilities:,}"
        )

    def test_source_xbrl_url_present(self, ten_k_result):
        case, result = ten_k_result
        assert result.get("source_xbrl_url"), (
            f"{case['company']}: source_xbrl_url missing"
        )


# ---------------------------------------------------------------------------
# 13F fixtures  (holding counts confirmed from EDGAR on 2026-06-09)
# ---------------------------------------------------------------------------

THIRTEEN_F_CASES = [
    {
        "id":           "blackrock_q2_2024",
        "institution":  "BlackRock",
        "url":          "https://www.sec.gov/Archives/edgar/data/1364742/000108636424008417/0001086364-24-008417-index.htm",
        "min_holdings": 1000,   # confirmed: 48,161
    },
    {
        "id":           "vanguard_2025",
        "institution":  "Vanguard",
        "url":          "https://www.sec.gov/Archives/edgar/data/102909/000010290926000031/0000102909-26-000031-index.htm",
        "min_holdings": 500,    # confirmed: 17,686
    },
]


@pytest.fixture(
    scope="module",
    params=THIRTEEN_F_CASES,
    ids=[c["id"] for c in THIRTEEN_F_CASES],
)
def thirteen_f_holdings(request):
    case = request.param
    holdings = _skip_on_rate_limit(extract_13f_holdings, case["url"])
    return case, holdings


class TestDataset13F:
    """Parametrised 13F extraction for two large institutional filers."""

    def test_returns_list(self, thirteen_f_holdings):
        _, holdings = thirteen_f_holdings
        assert isinstance(holdings, list)

    def test_minimum_holding_count(self, thirteen_f_holdings):
        case, holdings = thirteen_f_holdings
        assert len(holdings) >= case["min_holdings"], (
            f"{case['institution']}: expected >={case['min_holdings']} holdings, "
            f"got {len(holdings)}"
        )

    def test_holding_schema(self, thirteen_f_holdings):
        case, holdings = thirteen_f_holdings
        required = {"issuer", "class", "cusip", "value_usd_thousands", "shares"}
        for h in holdings[:10]:
            assert required.issubset(h.keys()), (
                f"{case['institution']}: holding missing keys: {h}"
            )

    def test_cusips_are_9_chars(self, thirteen_f_holdings):
        case, holdings = thirteen_f_holdings
        bad = [h for h in holdings if h["cusip"] != "UNKNOWN" and len(h["cusip"]) != 9]
        assert not bad, (
            f"{case['institution']}: malformed CUSIPs: {bad[:3]}"
        )

    def test_all_values_non_negative(self, thirteen_f_holdings):
        case, holdings = thirteen_f_holdings
        for h in holdings:
            assert h["value_usd_thousands"] >= 0, (
                f"{case['institution']}: negative value: {h}"
            )
            assert h["shares"] >= 0, (
                f"{case['institution']}: negative shares: {h}"
            )
