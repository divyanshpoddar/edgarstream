"""
Golden-file regression tests for the S-1 heuristic parser.
"""
import pytest
import respx
from httpx import Response
from pathlib import Path

FIXTURES = Path(__file__).parent / "fixtures"
INDEX_URL = "https://www.sec.gov/Archives/edgar/data/999999/000099999926000001/0000999999-26-000001-index.htm"
DOC_URL = "https://www.sec.gov/Archives/edgar/data/999999/000099999926000001/forms-1.htm"

INDEX_HTML = (FIXTURES / "s1_index.html").read_bytes()
DOC_HTML = (FIXTURES / "s1_document.html").read_bytes()


@respx.mock
def test_price_range_extracted():
    respx.get(INDEX_URL).mock(return_value=Response(200, content=INDEX_HTML))
    respx.get(DOC_URL).mock(return_value=Response(200, content=DOC_HTML))

    from services.parser.form_s1 import extract_s1_data
    result = extract_s1_data(INDEX_URL)

    assert result["offering_price_low"] == 14.0
    assert result["offering_price_high"] == 16.0


@respx.mock
def test_shares_offered_extracted():
    respx.get(INDEX_URL).mock(return_value=Response(200, content=INDEX_HTML))
    respx.get(DOC_URL).mock(return_value=Response(200, content=DOC_HTML))

    from services.parser.form_s1 import extract_s1_data
    result = extract_s1_data(INDEX_URL)

    assert result["shares_offered"] == 10_000_000


@respx.mock
def test_revenue_extracted_from_table():
    respx.get(INDEX_URL).mock(return_value=Response(200, content=INDEX_HTML))
    respx.get(DOC_URL).mock(return_value=Response(200, content=DOC_HTML))

    from services.parser.form_s1 import extract_s1_data
    result = extract_s1_data(INDEX_URL)

    assert result["recent_revenue"] is not None
    assert result["recent_revenue"] > 0


@respx.mock
def test_no_price_range_returns_none():
    doc_no_price = b"<html><body><p>We are offering shares of common stock being offered hereby.</p></body></html>"
    respx.get(INDEX_URL).mock(return_value=Response(200, content=INDEX_HTML))
    respx.get(DOC_URL).mock(return_value=Response(200, content=doc_no_price))

    from services.parser.form_s1 import extract_s1_data
    result = extract_s1_data(INDEX_URL)

    assert result["offering_price_low"] is None
    assert result["offering_price_high"] is None


@respx.mock
def test_source_url_recorded():
    respx.get(INDEX_URL).mock(return_value=Response(200, content=INDEX_HTML))
    respx.get(DOC_URL).mock(return_value=Response(200, content=DOC_HTML))

    from services.parser.form_s1 import extract_s1_data
    result = extract_s1_data(INDEX_URL)

    assert result["source_url"] == DOC_URL


@respx.mock
def test_missing_s1_document_link():
    """Index page with no S-1 link returns all-None result."""
    bad_index = b"<html><body><table><tr><td>1</td><td>d</td><td><a href='/f.htm'>f.htm</a></td><td>EX-99.1</td><td>8K</td></tr></table></body></html>"
    respx.get(INDEX_URL).mock(return_value=Response(200, content=bad_index))

    from services.parser.form_s1 import extract_s1_data
    result = extract_s1_data(INDEX_URL)

    assert result["offering_price_low"] is None
    assert result["shares_offered"] is None


def test_price_range_regex_directly():
    """Unit test the regex helper without HTTP calls."""
    from services.parser.form_s1 import _parse_offering_price

    lo, hi = _parse_offering_price("The price range is $18.00 to $21.00 per share.")
    assert lo == 18.0
    assert hi == 21.0


def test_shares_regex_directly():
    from services.parser.form_s1 import _parse_shares_offered

    # Regex requires "Class A/B" designation or plain "being offered hereby"
    shares = _parse_shares_offered(
        "We are offering 5,000,000 shares of our Class A common stock being offered hereby."
    )
    assert shares == 5_000_000
