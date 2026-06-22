# services/listener/rss_poller.py
import time
import re
import feedparser
import json
import logging
import os 
from datetime import datetime, timezone, UTC
import httpx
from dotenv import load_dotenv
from redis import Redis
from shared.models.filing import SECFilingMetadata

load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Only ingest form types we have parsers for. Avoids flooding the queue
# with hundreds of Form 4s and DEF14As during market hours.
SUPPORTED_FORM_TYPES = {"10-K", "10-Q", "8-K", "13F-HR", "13F-HR/A", "S-1", "S-1/A"}

SEC_RSS_URL = "https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=&company=&dateb=&owner=include&start=0&count=40&output=atom"

# Update host to localhost for your local machine, or the container name if running inside docker
load_dotenv()

redis_client = Redis(
    host=os.getenv("REDIS_HOST", "localhost"),
    port=int(os.getenv("REDIS_PORT", 6379)),
    password=os.getenv("REDIS_PASSWORD", None),
    ssl=os.getenv("REDIS_SSL", "false").lower() == "true",
    db=0,
    decode_responses=True,
)

SEEN_FILINGS_SET = "edgarstream:seen_accession_numbers"
FILING_QUEUE = "edgarstream:filing_queue"

def extract_field_via_regex(entry) -> tuple[str, str, str]:
    """
    Robust extraction of Form Type, Company Name, and CIK from feed data.
    Titles look like: "4 - Apple Inc. (0000320193) (Issuer)"
    """
    title = entry.get('title', '')
    form_type = "UNKNOWN"
    company_name = "UNKNOWN"
    cik = "UNKNOWN"
    
    # Extract form type: everything before the first hyphen
    if " - " in title:
        form_type = title.split(" - ")[0].strip()
        
    # Extract Company Name and CIK using regex from title
    # Matches: Form - Company Name (0000000000)
    match = re.search(r' -\s+(.*?)\s+\((\d{10})\)', title)
    if match:
        company_name = match.group(1).strip()
        cik = match.group(2).strip()
    else:
        # Fallback if title formatting shifts
        summary = entry.get('summary', '')
        cik_match = re.search(r'CIK=(\d{10})', summary)
        if cik_match:
            cik = cik_match.group(1)
            
    return form_type, company_name, cik

def parse_sec_feed():
    logger.info("Polling SEC EDGAR feed...")
    headers = {"User-Agent": "EdgarStreamProject professional-intelligence@firm.com"} 
    
    try:
        response = httpx.get(SEC_RSS_URL, headers=headers, timeout=10.0)
        response.raise_for_status()
    except Exception as e:
        logger.error(f"Failed to fetch SEC feed: {e}")
        return

    feed = feedparser.parse(response.text)
    new_filings_count = 0

    for entry in feed.entries:
        try:
            url = entry.get('link', '')
            if not url:
                continue
                
            accession_number = url.split('/')[-1].replace('-index.htm', '')
            
            # Idempotency barrier
            if redis_client.sismember(SEEN_FILINGS_SET, accession_number):
                continue
            
            form_type, company_name, cik = extract_field_via_regex(entry)
            
            if form_type not in SUPPORTED_FORM_TYPES:
                continue

            filing_metadata = SECFilingMetadata(
                accession_number=accession_number,
                cik=cik,
                company_name=company_name,
                form_type=form_type,
                filing_date=entry.get('updated', datetime.now(UTC).isoformat()),
                document_url=url
            )
            
            redis_client.lpush(FILING_QUEUE, filing_metadata.model_dump_json())
            redis_client.sadd(SEEN_FILINGS_SET, accession_number)
            
            new_filings_count += 1
            logger.info(f"Queued [{form_type}] {company_name} (CIK: {cik})")
            
        except Exception as e:
            logger.warning(f"Error parsing feed entry: {e}")
            
    logger.info(f"Poll complete. Queued {new_filings_count} clean filings.")

if __name__ == "__main__":
    while True:
        parse_sec_feed()
        time.sleep(30) # For dev speed, poll faster. Real production uses 300-600s.
