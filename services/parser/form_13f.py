# services/parser/form_13f.py
import logging
import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# The SEC requires a User-Agent in this format to avoid 403 Forbidden errors
HEADERS = {"User-Agent": "EdgarStreamProject professional-intelligence@firm.com"}

def extract_13f_holdings(index_url: str) -> list[dict]:
    """
    Given a 13F filing index URL, locates the XML information table, 
    downloads it, and extracts the structured portfolio holdings data.
    """
    try:
        # 1. Fetch the primary index landing page
        resp = httpx.get(index_url, headers=HEADERS, timeout=10.0)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.content, "lxml")
        
        # 2. Find the XML information table link
        # 13F filings contain a primary cover page xml and an information table xml.
        # We need to extract the information table containing the actual asset ledger.
        xml_url = None
        for row in soup.find_all("tr"):
            cells = row.find_all("td")
            if len(cells) > 2:
                document_type = cells[3].text.strip().lower()
                document_name = cells[2].text.strip().lower()
                
                # Check both type and name columns for standard SEC information table signatures
                if "information table" in document_type or "informationtable" in document_name:
                    link = cells[2].find("a")
                    if link:
                        xml_url = "https://www.sec.gov" + link["href"]
                        break
        
        if not xml_url:
            logger.warning(f"Could not find XML information table in {index_url}")
            return []

        # SEC wraps some 13F XMLs in an XSL-formatted HTML viewer under the
        # xslForm13F_X02/ subdirectory. Strip that prefix to get the raw XML,
        # which has proper <infoTable> elements parseable by BeautifulSoup.
        xml_url = xml_url.replace("/xslForm13F_X02/", "/")

        # 3. Fetch the raw XML data table
        xml_resp = httpx.get(xml_url, headers=HEADERS, timeout=10.0)
        xml_resp.raise_for_status()
        
        # 4. Parse the unstructured XML payload
        # SEC schemas enforce strict tags, parsed safely here with lxml-xml
        xml_soup = BeautifulSoup(xml_resp.content, "lxml-xml")
        
        holdings = []
        # Locate all individual asset records defined under infoTable tags
        for info in xml_soup.find_all("infoTable"):
            name_of_issuer = info.find("nameOfIssuer").text.strip() if info.find("nameOfIssuer") else "UNKNOWN"
            title_of_class = info.find("titleOfClass").text.strip() if info.find("titleOfClass") else "UNKNOWN"
            cusip = info.find("cusip").text.strip() if info.find("cusip") else "UNKNOWN"
            
            # Numeric fields use string-to-integer conversion fallback protection
            value = int(info.find("value").text.strip()) if info.find("value") else 0
            
            shrs_or_prn_amt = info.find("shrsOrPrnAmt")
            ssh_prnamt = int(shrs_or_prn_amt.find("sshPrnamt").text.strip()) if shrs_or_prn_amt and shrs_or_prn_amt.find("sshPrnamt") else 0
            
            holdings.append({
                "issuer": name_of_issuer,
                "class": title_of_class,
                "cusip": cusip,
                "value_usd_thousands": value,
                "shares": ssh_prnamt
            })
            
        logger.info(f"Successfully extracted {len(holdings)} holdings rows from 13F filing: {index_url}")
        return holdings

    except Exception as e:
        logger.error(f"Failed to extract 13F from {index_url}: {str(e)}")
        raise e