# tests/test_parser_13f.py
import httpx
from services.parser.form_13f import extract_13f_holdings

# --- 1. MOCK DATA (Fake SEC Responses) ---

# Fake Index Page containing a link to our fake XML
MOCK_INDEX_HTML = """
<html>
    <body>
        <table>
            <tr>
                <td>1</td>
                <td>Primary Document</td>
                <td><a href="/primary.xml">primary.xml</a></td>
                <td>13F-HR</td>
            </tr>
            <tr>
                <td>2</td>
                <td>Information Table</td>
                <td><a href="/fake_informationtable.xml">fake_informationtable.xml</a></td>
                <td>INFORMATION TABLE</td>
            </tr>
        </table>
    </body>
</html>
"""

# Fake 13F XML containing 3 test scenarios
MOCK_XML_DATA = """<?xml version="1.0"?>
<informationTable xmlns="http://www.sec.gov/edgar/document/thirteenf/informationtable">
    <infoTable>
        <nameOfIssuer>APPLE INC</nameOfIssuer>
        <titleOfClass>COM</titleOfClass>
        <cusip>037833100</cusip>
        <value>150000</value>
        <shrsOrPrnAmt>
            <sshPrnamt>1000</sshPrnamt>
        </shrsOrPrnAmt>
    </infoTable>
    
    <infoTable>
        <nameOfIssuer>MICROSOFT CORP</nameOfIssuer>
        <value>250000</value>
        <shrsOrPrnAmt>
            <sshPrnamt>5000</sshPrnamt>
        </shrsOrPrnAmt>
    </infoTable>
    
    <infoTable>
        <nameOfIssuer>TESLA INC</nameOfIssuer>
        <titleOfClass>COM</titleOfClass>
        <cusip>88160R101</cusip>
    </infoTable>
</informationTable>
"""

# --- 2. THE MOCKING INTERCEPTOR ---
class MockResponse:
    def __init__(self, content, status_code=200):
        self.content = content
        self.status_code = status_code
        
    def raise_for_status(self):
        pass

def mock_httpx_get(url, *args, **kwargs):
    """Intercepts requests to the SEC and returns our fake data."""
    if "index" in url:
        return MockResponse(MOCK_INDEX_HTML.encode('utf-8'))
    elif "fake_informationtable.xml" in url:
        return MockResponse(MOCK_XML_DATA.encode('utf-8'))
    return MockResponse(b"")

# --- 3. THE TEST RUNNER ---
def run_13f_tests():
    # Scoped mock — only active during this function, never at import time.
    original_get = httpx.get
    httpx.get = mock_httpx_get
    print("=" * 60)
    print("   SEC 13F XML PARSER TEST RUNNER (MOCKED)")
    print("=" * 60)
    
    # Pass a fake URL, our interceptor will catch it
    fake_url = "https://www.sec.gov/fake_index.htm"
    holdings = extract_13f_holdings(fake_url)
    
    passed_tests = 0
    failures = []

    # Test 1: Did it find all 3 holdings?
    if len(holdings) == 3:
        print("✅ Test 1: Extracted correct number of holdings (3)")
        passed_tests += 1
    else:
        failures.append(f"Test 1 FAILED: Expected 3 holdings, got {len(holdings)}")

    # Test 2: Did it extract Apple correctly?
    apple = holdings[0]
    if apple["issuer"] == "APPLE INC" and apple["shares"] == 1000 and apple["value_usd_thousands"] == 150000:
        print("✅ Test 2: Perfect Data Extraction (Apple)")
        passed_tests += 1
    else:
        failures.append(f"Test 2 FAILED: Apple data incorrect: {apple}")

    # Test 3: Did it handle Microsoft's missing fields gracefully?
    msft = holdings[1]
    if msft["issuer"] == "MICROSOFT CORP" and msft["class"] == "UNKNOWN" and msft["cusip"] == "UNKNOWN":
        print("✅ Test 3: Missing Fields Fallback (Microsoft)")
        passed_tests += 1
    else:
        failures.append(f"Test 3 FAILED: Fallback logic failed on Microsoft: {msft}")

    # Test 4: Did it handle Tesla's missing numbers gracefully?
    tsla = holdings[2]
    if tsla["issuer"] == "TESLA INC" and tsla["value_usd_thousands"] == 0 and tsla["shares"] == 0:
        print("✅ Test 4: Missing Numbers Fallback (Tesla)")
        passed_tests += 1
    else:
        failures.append(f"Test 4 FAILED: Number fallback failed on Tesla: {tsla}")

    print("=" * 60)
    if failures:
        print(f"❌ {len(failures)} FAILURES DETECTED")
        for f in failures:
            print(f"  {f}")
    else:
        print(f"🚀 {passed_tests}/4 TESTS PASSED! 13F XML Parser is robust.")

    httpx.get = original_get  # always restore — prevents polluting pytest sessions

if __name__ == "__main__":
    run_13f_tests()