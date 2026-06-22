"""
Golden-file regression tests for the 13F XML parser.
"""
import respx
from httpx import Response
from pathlib import Path

FIXTURES = Path(__file__).parent / "fixtures"
INDEX_URL = "https://www.sec.gov/Archives/edgar/data/1067983/000095012326000001/0000950123-26-000001-index.htm"
XML_URL = "https://www.sec.gov/Archives/edgar/data/1067983/000095012326000001/informationtable.xml"

INDEX_HTML = (FIXTURES / "13f_index.html").read_bytes()
TABLE_XML = (FIXTURES / "13f_table.xml").read_bytes()


@respx.mock
def test_holdings_count():
    respx.get(INDEX_URL).mock(return_value=Response(200, content=INDEX_HTML))
    respx.get(XML_URL).mock(return_value=Response(200, content=TABLE_XML))

    from services.parser.form_13f import extract_13f_holdings
    holdings = extract_13f_holdings(INDEX_URL)

    assert len(holdings) == 3


@respx.mock
def test_holding_fields_present():
    respx.get(INDEX_URL).mock(return_value=Response(200, content=INDEX_HTML))
    respx.get(XML_URL).mock(return_value=Response(200, content=TABLE_XML))

    from services.parser.form_13f import extract_13f_holdings
    holdings = extract_13f_holdings(INDEX_URL)

    for h in holdings:
        assert "issuer" in h
        assert "cusip" in h
        assert "value_usd_thousands" in h
        assert "shares" in h


@respx.mock
def test_apple_holding_values():
    respx.get(INDEX_URL).mock(return_value=Response(200, content=INDEX_HTML))
    respx.get(XML_URL).mock(return_value=Response(200, content=TABLE_XML))

    from services.parser.form_13f import extract_13f_holdings
    holdings = extract_13f_holdings(INDEX_URL)

    apple = next(h for h in holdings if h["issuer"] == "APPLE INC")
    assert apple["cusip"] == "037833100"
    assert apple["value_usd_thousands"] == 50_000_000
    assert apple["shares"] == 300_000


@respx.mock
def test_empty_xml_returns_empty_list():
    empty_xml = b"<?xml version='1.0'?><informationTable></informationTable>"
    respx.get(INDEX_URL).mock(return_value=Response(200, content=INDEX_HTML))
    respx.get(XML_URL).mock(return_value=Response(200, content=empty_xml))

    from services.parser.form_13f import extract_13f_holdings
    holdings = extract_13f_holdings(INDEX_URL)

    assert holdings == []


@respx.mock
def test_missing_xml_link_returns_empty_list():
    bad_index = b"<html><body><table><tr><td>1</td><td>Cover</td><td><a href='/cover.xml'>cover.xml</a></td><td>13F-HR</td><td>8K</td></tr></table></body></html>"
    respx.get(INDEX_URL).mock(return_value=Response(200, content=bad_index))

    from services.parser.form_13f import extract_13f_holdings
    holdings = extract_13f_holdings(INDEX_URL)

    assert holdings == []


@respx.mock
def test_holdings_are_sorted_deterministically():
    """Same XML always produces same ordering (list is stable)."""
    respx.get(INDEX_URL).mock(return_value=Response(200, content=INDEX_HTML))
    respx.get(XML_URL).mock(return_value=Response(200, content=TABLE_XML))

    from services.parser.form_13f import extract_13f_holdings
    h1 = extract_13f_holdings(INDEX_URL)

    respx.get(INDEX_URL).mock(return_value=Response(200, content=INDEX_HTML))
    respx.get(XML_URL).mock(return_value=Response(200, content=TABLE_XML))
    h2 = extract_13f_holdings(INDEX_URL)

    assert [h["cusip"] for h in h1] == [h["cusip"] for h in h2]
