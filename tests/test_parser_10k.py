# tests/test_parser_10k.py
from services.parser.form_10k import extract_10k_financials
import json

def test_apple_10k():
    print("=" * 60)
    print("   INITIATING ARELLE XBRL ENGINE (Testing Apple 10-K)")
    print("=" * 60)
    
    # Apple's actual 2023 10-K Index URL
    apple_url = "https://www.sec.gov/Archives/edgar/data/320193/000032019323000106/0000320193-23-000106-index.htm"
    
    financials = extract_10k_financials(apple_url)
    
    print("\n✅ EXTRACTION COMPLETE. RAW DATA:")
    print(json.dumps(financials, indent=4))
    
    if financials.get("Revenues") == 383285000000:
        print("\n🚀 SUCCESS: Extracted perfect consolidated XBRL data!")
    else:
        print("\n❌ FAILURE: XBRL context parsing missed the target value.")

if __name__ == "__main__":
    test_apple_10k()