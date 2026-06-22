# services/parser/form_10q.py
import logging
import datetime
import httpx
from bs4 import BeautifulSoup
from arelle import Cntlr

# Re-use shared helpers from the 10-K parser
from services.parser.form_10k import (
    HeadlessArelle,
    _find_instance_url,
    _document_period_end,
    _ctx_end_date,
    _LINKBASE_TYPES,
)

logger = logging.getLogger(__name__)
HEADERS = {"User-Agent": "EdgarStreamProject professional-intelligence@firm.com"}


def _find_10q_instance_url(index_url: str) -> str | None:
    """Same as 10-K version but falls back to the 10-Q primary document."""
    resp = httpx.get(index_url, headers=HEADERS, timeout=10.0)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.content, "lxml")

    inline_fallback = None

    for row in soup.find_all("tr"):
        cells = row.find_all("td")
        if len(cells) <= 3:
            continue

        desc = cells[1].get_text(strip=True).lower()
        doc_type = cells[3].get_text(strip=True).upper()

        link = cells[2].find("a")
        if not link or not link.get("href"):
            continue

        href = link["href"]
        if href.startswith("/ix?doc="):
            href = href.split("=", 1)[1]
        url = "https://www.sec.gov" + href
        fname = href.rsplit("/", 1)[-1].lower()

        if doc_type in _LINKBASE_TYPES:
            continue

        if (doc_type == "EX-101.INS"
                or "instance document" in desc
                or fname.endswith("_htm.xml")):
            return url

        if doc_type == "10-Q" and fname.endswith(".htm"):
            inline_fallback = url

    return inline_fallback


def _matches_quarterly_period(ctx, period_end: datetime.date | None) -> bool:
    """
    Accept only the current quarter's context.
    Quarterly duration: 75–97 days (handles 13-week fiscal quarters).
    Balance-sheet instants at period-end are always accepted.
    """
    if period_end is None:
        return True
    end = _ctx_end_date(ctx)
    if end is None or abs((end - period_end).days) > 4:
        return False
    if ctx.isInstantPeriod:
        return True
    if ctx.startDatetime is None:
        return True
    days = (end - ctx.startDatetime.date()).days
    return 75 <= days <= 97


def extract_10q_financials(index_url: str) -> dict:
    """
    Locates the XBRL instance document for a 10-Q filing, loads it into Arelle,
    and extracts the current-quarter consolidated financial statement items.
    Returns the same schema as extract_10k_financials for consistent Snowflake loading.
    """
    try:
        xbrl_url = _find_10q_instance_url(index_url)
        if not xbrl_url:
            logger.warning(f"Could not find XBRL instance document in {index_url}")
            return {}

        logger.info(f"Parsing 10-Q XBRL instance from {xbrl_url}...")
        ctrl = HeadlessArelle()
        ctrl.startLogging(logFileName="logToPrint", logLevel="ERROR")
        model_xbrl = ctrl.modelManager.load(xbrl_url)
        if model_xbrl is None:
            logger.error(f"Arelle failed to load {xbrl_url}")
            return {}

        period_end = _document_period_end(model_xbrl)

        concept_mappings = {
            "Assets": {"assets"},
            "Liabilities": {"liabilities"},
            "Revenues": {
                "revenues",
                "revenuefromcontractwithcustomerexcludingassessedtax",
                "salesrevenuenet",
            },
            "NetIncomeLoss": {"netincomeloss", "profitloss"},
        }
        financials = {metric: 0 for metric in concept_mappings}
        tag_provenance: dict[str, str] = {}

        for fact in model_xbrl.facts:
            if fact.isNil or not fact.value:
                continue

            ns_uri = (getattr(fact.qname, "namespaceURI", "") or "").lower()
            if "us-gaap" not in ns_uri:
                continue

            ctx = fact.context
            if ctx is None or ctx.qnameDims:
                continue
            if not _matches_quarterly_period(ctx, period_end):
                continue

            local_name = (fact.qname.localName or "").lower()
            for metric, aliases in concept_mappings.items():
                if local_name in aliases:
                    try:
                        financials[metric] = int(float(fact.value))
                        tag_provenance[metric] = fact.qname.localName
                    except (ValueError, TypeError):
                        pass
                    break

        ctrl.modelManager.close()
        financials["source_xbrl_url"] = xbrl_url
        financials["tag_provenance"] = tag_provenance
        logger.info(f"Successfully extracted 10-Q financials from {index_url}")
        return financials

    except Exception as e:
        logger.error(f"Failed to extract 10-Q XBRL from {index_url}: {str(e)}")
        return {}
