"""
S-1 / S-1/A registration statement parser.

S-1s are IPO filings. Unlike 10-K/10-Q they carry no mandatory XBRL, so this
parser uses HTML heuristics to extract:
  - offering_price_low / offering_price_high  (cover-page price range)
  - shares_offered                            (total shares in the offering)
  - recent_revenue                            (from financial highlights)
  - recent_net_income                         (loss is negative)
  - company_description                       (one-line business summary)
"""
import logging
import re

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)
HEADERS = {"User-Agent": "EdgarStreamProject professional-intelligence@firm.com"}

# Regex patterns -----------------------------------------------------------

# Matches "$12.00 to $15.00 per share" or "$12.00-$15.00"
_PRICE_RANGE = re.compile(
    r"\$\s*([\d,]+(?:\.\d+)?)\s*(?:to|–|-)\s*\$\s*([\d,]+(?:\.\d+)?)\s*per\s*share",
    re.IGNORECASE,
)

# Matches "X,XXX,XXX shares" near "offering" or "offered"
_SHARES_OFFERED = re.compile(
    r"([\d,]+)\s*shares?\s*(?:of\s+(?:our\s+)?class\s+[A-Z]\s+)?(?:common\s+stock\s+)?(?:in\s+this\s+offering|being\s+offered|offered\s+hereby)",
    re.IGNORECASE,
)

# Dollar amounts in financial tables — captures e.g. "383,285" or "383,285,000"
_DOLLAR_AMOUNT = re.compile(r"\$?\s*([\d,]+(?:\.\d+)?)")


def _find_main_document_url(index_url: str) -> str | None:
    """Return the URL of the primary S-1 HTML document from the filing index."""
    resp = httpx.get(index_url, headers=HEADERS, timeout=10.0)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.content, "lxml")

    for row in soup.find_all("tr"):
        cells = row.find_all("td")
        if len(cells) <= 3:
            continue
        doc_type = cells[3].get_text(strip=True).upper()
        if doc_type not in ("S-1", "S-1/A"):
            continue
        link = cells[2].find("a")
        if link and link.get("href"):
            href = link["href"]
            if href.startswith("/ix?doc="):
                href = href.split("=", 1)[1]
            return "https://www.sec.gov" + href

    return None


def _parse_offering_price(text: str) -> tuple[float | None, float | None]:
    m = _PRICE_RANGE.search(text)
    if not m:
        return None, None
    try:
        lo = float(m.group(1).replace(",", ""))
        hi = float(m.group(2).replace(",", ""))
        return lo, hi
    except ValueError:
        return None, None


def _parse_shares_offered(text: str) -> int | None:
    m = _SHARES_OFFERED.search(text)
    if not m:
        return None
    try:
        return int(m.group(1).replace(",", ""))
    except ValueError:
        return None


def _find_revenue_in_tables(soup: BeautifulSoup) -> int | None:
    """
    Scan financial summary tables for the most recent revenue row.
    Looks for rows containing 'revenue' near the top of financial tables.
    """
    for table in soup.find_all("table"):
        rows = table.find_all("tr")
        for row in rows:
            cells = row.find_all(["td", "th"])
            row_text = " ".join(c.get_text(strip=True) for c in cells).lower()
            if "revenue" not in row_text and "net revenue" not in row_text:
                continue
            # Find numeric cells in this row
            for cell in cells:
                text = cell.get_text(strip=True).replace(",", "").replace("$", "").replace("(", "-").replace(")", "")
                try:
                    val = int(float(text))
                    if abs(val) > 1_000:   # ignore tiny numbers
                        return val
                except ValueError:
                    continue
    return None


def extract_s1_data(index_url: str) -> dict:
    """
    Extract structured data from an S-1 or S-1/A registration statement.

    Returns a dict with keys:
      offering_price_low, offering_price_high, shares_offered,
      recent_revenue, recent_net_income, source_url
    All fields are None when the heuristic couldn't find a value.
    """
    result: dict = {
        "offering_price_low":  None,
        "offering_price_high": None,
        "shares_offered":      None,
        "recent_revenue":      None,
        "recent_net_income":   None,
        "source_url":          index_url,
    }

    try:
        doc_url = _find_main_document_url(index_url)
        if not doc_url:
            logger.warning("Could not find S-1 primary document in %s", index_url)
            return result

        logger.info("Parsing S-1 document: %s", doc_url)
        resp = httpx.get(doc_url, headers=HEADERS, timeout=20.0)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.content, "lxml")
        full_text = soup.get_text(separator=" ")

        lo, hi = _parse_offering_price(full_text)
        result["offering_price_low"]  = lo
        result["offering_price_high"] = hi

        result["shares_offered"] = _parse_shares_offered(full_text)
        result["recent_revenue"] = _find_revenue_in_tables(soup)
        result["source_url"]     = doc_url

        logger.info(
            "S-1 extracted: price=[$%.2f-$%.2f] shares=%s revenue=%s",
            lo or 0, hi or 0, result["shares_offered"], result["recent_revenue"],
        )

    except Exception as exc:
        logger.error("S-1 extraction failed for %s: %s", index_url, exc)

    return result
