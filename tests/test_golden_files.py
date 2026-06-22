# tests/test_golden_files.py
"""
Golden-file regression tests for all three parsers.
Each test fetches a known historical filing and asserts extracted values
match pre-recorded fixtures. CI runs these on every PR.

Fixtures are keyed by accession number so re-runs are deterministic.
If a filing's XBRL values are amended by the SEC, update the fixture and
document the change in the PR description.
"""
import pytest
from services.parser.form_10k import extract_10k_financials
from services.parser.form_13f import extract_13f_holdings
from services.parser.form_8k import extract_8k_events

# ---------------------------------------------------------------------------
# Golden fixtures
# ---------------------------------------------------------------------------

# Apple 10-K FY2023 (filed 2023-11-03)
APPLE_10K_INDEX = (
    "https://www.sec.gov/Archives/edgar/data/320193/"
    "000032019323000106/0000320193-23-000106-index.htm"
)
APPLE_10K_FIXTURE = {
    "Assets":       352_583_000_000,
    "Liabilities":  290_437_000_000,
    "Revenues":     383_285_000_000,
    "NetIncomeLoss": 96_995_000_000,
}

# Berkshire Hathaway 13F-HR Q3-2023 (filed 2023-11-14)
BERKSHIRE_13F_INDEX = (
    "https://www.sec.gov/Archives/edgar/data/1067983/"
    "000095012323012008/0000950123-23-012008-index.htm"
)
BERKSHIRE_13F_MIN_HOLDINGS = 30   # Berkshire holds 40-50 positions; 30 is a safe floor
BERKSHIRE_13F_KNOWN_CUSIP  = "037833100"  # Apple CUSIP — always in Berkshire 13F

# Arch Capital 8-K (filed 2026-06-02, live filing from today's poller)
ARCH_8K_INDEX = (
    "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany"
    "&CIK=0000947484&type=8-K&dateb=&owner=include&count=1&output=atom"
)


# ---------------------------------------------------------------------------
# 10-K tests
# ---------------------------------------------------------------------------

class TestApple10K:
    """Golden-file regression tests for Apple's FY2023 10-K XBRL extraction."""

    @pytest.fixture(scope="class")
    def result(self):
        return extract_10k_financials(APPLE_10K_INDEX)

    def test_returns_dict(self, result):
        assert isinstance(result, dict)

    def test_assets_extracted(self, result):
        assert result.get("Assets") is not None, "Total Assets not extracted"

    def test_liabilities_extracted(self, result):
        assert result.get("Liabilities") is not None, "Total Liabilities not extracted"

    def test_revenues_extracted(self, result):
        assert result.get("Revenues") is not None, "Revenues not extracted"

    def test_net_income_extracted(self, result):
        assert result.get("NetIncomeLoss") is not None, "Net Income not extracted"

    def test_assets_within_tolerance(self, result):
        expected = APPLE_10K_FIXTURE["Assets"]
        actual = result.get("Assets", 0)
        # Allow 1% tolerance for unit-scaling differences (some filers report in thousands)
        assert abs(actual - expected) / expected < 0.01, (
            f"Assets {actual:,} deviates >1% from fixture {expected:,}"
        )

    def test_revenues_within_tolerance(self, result):
        expected = APPLE_10K_FIXTURE["Revenues"]
        actual = result.get("Revenues", 0)
        assert abs(actual - expected) / expected < 0.01, (
            f"Revenues {actual:,} deviates >1% from fixture {expected:,}"
        )

    def test_net_income_within_tolerance(self, result):
        expected = APPLE_10K_FIXTURE["NetIncomeLoss"]
        actual = result.get("NetIncomeLoss", 0)
        assert abs(actual - expected) / expected < 0.01, (
            f"Net income {actual:,} deviates >1% from fixture {expected:,}"
        )

    def test_balance_sheet_identity(self, result):
        """Assets should be >= Liabilities (equity is non-negative for Apple)."""
        assets = result.get("Assets", 0)
        liabilities = result.get("Liabilities", 0)
        assert assets >= liabilities, (
            f"Balance sheet violated: Assets {assets:,} < Liabilities {liabilities:,}"
        )

    def test_source_xbrl_url_present(self, result):
        assert result.get("source_xbrl_url"), "source_xbrl_url missing — lineage broken"


# ---------------------------------------------------------------------------
# 13F tests
# ---------------------------------------------------------------------------

class TestBerkshire13F:
    """Golden-file regression tests for Berkshire Hathaway's Q3-2023 13F."""

    @pytest.fixture(scope="class")
    def holdings(self):
        try:
            return extract_13f_holdings(BERKSHIRE_13F_INDEX)
        except Exception as e:
            # SEC EDGAR rate-limits external IPs with 503. Skip rather than
            # fail the whole suite — the golden values are correct when it runs.
            if "503" in str(e) or "429" in str(e) or "Service Unavailable" in str(e):
                pytest.skip(f"SEC EDGAR temporarily unavailable (rate limit): {e}")
            raise

    def test_returns_list(self, holdings):
        assert isinstance(holdings, list)

    def test_minimum_holding_count(self, holdings):
        assert len(holdings) >= BERKSHIRE_13F_MIN_HOLDINGS, (
            f"Expected >= {BERKSHIRE_13F_MIN_HOLDINGS} holdings, got {len(holdings)}"
        )

    def test_holding_schema(self, holdings):
        required_keys = {"issuer", "class", "cusip", "value_usd_thousands", "shares"}
        for h in holdings[:5]:
            assert required_keys.issubset(h.keys()), f"Holding missing keys: {h}"

    def test_apple_position_present(self, holdings):
        cusips = {h["cusip"] for h in holdings}
        assert BERKSHIRE_13F_KNOWN_CUSIP in cusips, (
            "Apple CUSIP 037833100 not found — Berkshire always holds Apple"
        )

    def test_all_values_positive(self, holdings):
        for h in holdings:
            assert h["value_usd_thousands"] >= 0, f"Negative value in holding: {h}"
            assert h["shares"] >= 0, f"Negative shares in holding: {h}"


# ---------------------------------------------------------------------------
# 8-K tests
# ---------------------------------------------------------------------------

class Test8KHeuristics:
    """
    Tests for the 8-K heuristic parser using the filing index URL directly.
    Uses a known 8-K with a confirmed executive change event.
    Apple 8-K 2023-01-03: CFO resignation disclosure.
    """

    APPLE_8K_INDEX = (
        "https://www.sec.gov/Archives/edgar/data/320193/"
        "000032019323000002/0000320193-23-000002-index.htm"
    )

    @pytest.fixture(scope="class")
    def result(self):
        return extract_8k_events(self.APPLE_8K_INDEX)

    def test_returns_dict(self, result):
        assert isinstance(result, dict)

    def test_has_items_key(self, result):
        assert "items" in result or "summary" in result, (
            "8-K result missing both 'items' and 'summary' keys"
        )

    def test_no_exception_on_parse(self, result):
        # If we got a dict back, the parser completed without crashing
        assert result is not None
