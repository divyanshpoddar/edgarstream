"""
Golden-file regression tests for the 8-K heuristic parser.
All HTTP calls are intercepted by respx — no network required.
"""
import pytest
import respx
from httpx import Response
from pathlib import Path

FIXTURES = Path(__file__).parent / "fixtures"
INDEX_URL = "https://www.sec.gov/Archives/edgar/data/320193/000032019326000001/0000320193-26-000001-index.htm"
DOC_URL = "https://www.sec.gov/Archives/edgar/data/320193/000032019326000001/form8-k.htm"

INDEX_HTML = (FIXTURES / "8k_index.html").read_bytes()
EXEC_HTML = (FIXTURES / "8k_exec_change.html").read_bytes()
BANKRUPT_HTML = (FIXTURES / "8k_bankruptcy.html").read_bytes()


@respx.mock
def test_executive_change_via_item_number():
    respx.get(INDEX_URL).mock(return_value=Response(200, content=INDEX_HTML))
    respx.get(DOC_URL).mock(return_value=Response(200, content=EXEC_HTML))

    from services.parser.form_8k import extract_8k_events
    result = extract_8k_events(INDEX_URL)

    assert result["executive_changes"] is True
    assert "5.02" in result["item_numbers"]
    assert result["bankruptcy_or_receivership"] is False


@respx.mock
def test_bankruptcy_via_item_number():
    respx.get(INDEX_URL).mock(return_value=Response(200, content=INDEX_HTML))
    respx.get(DOC_URL).mock(return_value=Response(200, content=BANKRUPT_HTML))

    from services.parser.form_8k import extract_8k_events
    result = extract_8k_events(INDEX_URL)

    assert result["bankruptcy_or_receivership"] is True
    assert "1.03" in result["item_numbers"]
    assert result["executive_changes"] is False


@respx.mock
def test_executive_change_via_text_heuristic():
    html = b"<html><body><p>The CEO resigned effective immediately. The Board appointed a new director.</p></body></html>"
    respx.get(INDEX_URL).mock(return_value=Response(200, content=INDEX_HTML))
    respx.get(DOC_URL).mock(return_value=Response(200, content=html))

    from services.parser.form_8k import extract_8k_events
    result = extract_8k_events(INDEX_URL)

    assert result["executive_changes"] is True
    assert result["bankruptcy_or_receivership"] is False


@respx.mock
def test_no_special_events():
    html = b"<html><body><p>Item 8.01 Other Events. The company announces a new product line.</p></body></html>"
    respx.get(INDEX_URL).mock(return_value=Response(200, content=INDEX_HTML))
    respx.get(DOC_URL).mock(return_value=Response(200, content=html))

    from services.parser.form_8k import extract_8k_events
    result = extract_8k_events(INDEX_URL)

    assert result["executive_changes"] is False
    assert result["bankruptcy_or_receivership"] is False
    assert isinstance(result["item_numbers"], list)


@respx.mock
def test_missing_primary_document_link():
    """Index with no 8-K type row returns graceful empty dict."""
    index_no_link = b"<html><body><table><tr><td>1</td><td>desc</td><td>file.htm</td><td>EX-99.1</td><td>8K</td></tr></table></body></html>"
    respx.get(INDEX_URL).mock(return_value=Response(200, content=index_no_link))

    from services.parser.form_8k import extract_8k_events
    result = extract_8k_events(INDEX_URL)

    assert result["executive_changes"] is False
    assert result["bankruptcy_or_receivership"] is False
    assert result["item_numbers"] == []


@respx.mock
def test_result_is_idempotent():
    """Same filing processed twice returns identical output."""
    respx.get(INDEX_URL).mock(return_value=Response(200, content=INDEX_HTML))
    respx.get(DOC_URL).mock(return_value=Response(200, content=EXEC_HTML))

    from services.parser.form_8k import extract_8k_events
    r1 = extract_8k_events(INDEX_URL)

    respx.get(INDEX_URL).mock(return_value=Response(200, content=INDEX_HTML))
    respx.get(DOC_URL).mock(return_value=Response(200, content=EXEC_HTML))
    r2 = extract_8k_events(INDEX_URL)

    assert r1 == r2
