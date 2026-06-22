# services/parser/form_10k.py
import logging
import datetime
import httpx
from bs4 import BeautifulSoup
from arelle import Cntlr

logger = logging.getLogger(__name__)
HEADERS = {"User-Agent": "EdgarStreamProject professional-intelligence@firm.com"}

# Taxonomy/linkbase files contain NO instance facts. They must never be
# selected as the document to parse for financials.
_LINKBASE_TYPES = {"EX-101.SCH", "EX-101.CAL", "EX-101.DEF",
                   "EX-101.LAB", "EX-101.PRE"}


class HeadlessArelle(Cntlr.Cntlr):
    """A minimal, headless controller to run Arelle without its GUI."""
    def __init__(self):
        super().__init__(hasGui=False)


def _find_instance_url(index_url: str) -> str | None:
    """
    Pick the XBRL *instance* document from the EDGAR filing index.

    Priority:
      1. A document explicitly typed EX-101.INS (older, non-inline filings)
      2. A document whose description says 'instance document'
         (the EDGAR 'EXTRACTED XBRL INSTANCE DOCUMENT', named *_htm.xml)
      3. Fallback: the primary inline-XBRL .htm 10-K document itself
    Linkbase/schema files are skipped outright, which is the bug the old
    'any description containing "xbrl" ending in .xml' rule introduced.
    """
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
        # The primary 10-K viewer link looks like /ix?doc=/Archives/...htm
        if href.startswith("/ix?doc="):
            href = href.split("=", 1)[1]
        url = "https://www.sec.gov" + href
        fname = href.rsplit("/", 1)[-1].lower()  # robust vs trailing "iXBRL" text

        if doc_type in _LINKBASE_TYPES:
            continue

        if (doc_type == "EX-101.INS"
                or "instance document" in desc
                or fname.endswith("_htm.xml")):
            return url

        if doc_type == "10-K" and fname.endswith(".htm"):
            inline_fallback = url  # remember, but keep looking for a real instance

    return inline_fallback


def _document_period_end(model_xbrl) -> datetime.date | None:
    """Read dei:DocumentPeriodEndDate to learn which fiscal period to keep."""
    for fact in model_xbrl.facts:
        q = fact.qname
        if q is None or q.localName != "DocumentPeriodEndDate":
            continue
        if "dei" not in (getattr(q, "namespaceURI", "") or "").lower():
            continue
        try:
            return datetime.date.fromisoformat((fact.value or "").strip())
        except (ValueError, AttributeError):
            pass
    return None


def _ctx_end_date(ctx) -> datetime.date | None:
    """
    Arelle stores instant/end datetimes as exclusive (the reported date + 1 day),
    so subtract a day to recover the date as printed on the statement.
    """
    dt = ctx.instantDatetime if ctx.isInstantPeriod else ctx.endDatetime
    if dt is None:
        return None
    return (dt - datetime.timedelta(days=1)).date()


def _matches_reporting_period(ctx, period_end: datetime.date | None) -> bool:
    """Keep only the filing's reporting period; reject quarterly/comparative facts."""
    if period_end is None:
        return True  # best effort if we couldn't read the period end
    end = _ctx_end_date(ctx)
    if end is None or abs((end - period_end).days) > 4:
        return False
    if ctx.isInstantPeriod:
        return True  # balance-sheet item at period end
    # Duration item: require an annual span so quarterly figures are excluded.
    if ctx.startDatetime is None:
        return True
    days = (end - ctx.startDatetime.date()).days
    return 340 <= days <= 380  # Apple uses 52/53-week years (~364-371 days)


def extract_10k_financials(index_url: str) -> dict:
    """
    Locates the XBRL instance document, loads it into Arelle, and extracts the
    consolidated, current-period top-level financial statements.
    """
    try:
        xbrl_url = _find_instance_url(index_url)
        if not xbrl_url:
            logger.warning(f"Could not find XBRL instance document in {index_url}")
            return {}

        logger.info(f"Parsing XBRL instance from {xbrl_url}...")
        ctrl = HeadlessArelle()
        ctrl.startLogging(logFileName="logToPrint", logLevel="ERROR")
        model_xbrl = ctrl.modelManager.load(xbrl_url)
        if model_xbrl is None:
            logger.error(f"Arelle failed to load {xbrl_url}")
            return {}

        period_end = _document_period_end(model_xbrl)

        # Note: LiabilitiesAndStockholdersEquity is intentionally NOT an alias for
        # Liabilities -- by the balance-sheet identity it equals total Assets.
        concept_mappings = {
            "Assets": {"assets"},
            "Liabilities": {"liabilities"},
            "Revenues": {"revenues",
                         "revenuefromcontractwithcustomerexcludingassessedtax",
                         "salesrevenuenet"},
            "NetIncomeLoss": {"netincomeloss", "profitloss"},
        }
        financials = {metric: 0 for metric in concept_mappings}
        # Records the exact XBRL concept tag that produced each metric value,
        # e.g. {"Revenues": "RevenueFromContractWithCustomerExcludingAssessedTax"}
        tag_provenance: dict[str, str] = {}

        for fact in model_xbrl.facts:
            if fact.isNil or not fact.value:
                continue

            ns_uri = (getattr(fact.qname, "namespaceURI", "") or "").lower()
            if "us-gaap" not in ns_uri:
                continue

            ctx = fact.context
            if ctx is None:
                continue
            # Consolidated only: a context with segment/axis members is a
            # dimensional breakdown (by product, geography, etc.), not the total.
            if ctx.qnameDims:
                continue
            if not _matches_reporting_period(ctx, period_end):
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
        logger.info(f"Successfully extracted 10-K financials from {index_url}")
        return financials

    except Exception as e:
        logger.error(f"Failed to extract 10-K XBRL from {index_url}: {str(e)}")
        return {}