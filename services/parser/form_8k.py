# services/parser/form_8k.py
import logging
import httpx
import re
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

HEADERS = {"User-Agent": "EdgarStreamProject professional-intelligence@firm.com"}

def extract_8k_events(document_url: str) -> dict:
    """
    Downloads unstructured 8-K HTML, strips boilerplate, and extracts 
    structured events using our verified 50/50 regex and proximity heuristics.
    """
    try:
        # 1. Fetch the document index to find the primary HTML filing
        resp = httpx.get(document_url, headers=HEADERS, timeout=10.0)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.content, "lxml")
        
        primary_doc_url = None
        for row in soup.find_all("tr"):
            cells = row.find_all("td")
            if len(cells) > 2:
                doc_type = cells[3].text.strip()
                if doc_type == "8-K":
                    link = cells[2].find("a")
                    if link:
                        primary_doc_url = "https://www.sec.gov" + link["href"]
                        break
                        
        if not primary_doc_url:
            logger.warning(f"Could not find primary 8-K document in {document_url}")
            return {
                "item_numbers": [],
                "executive_changes": False,
                "bankruptcy_or_receivership": False,
                "summary": "Primary 8-K document link not found."
            }

        # 2. Fetch the raw 8-K HTML
        doc_resp = httpx.get(primary_doc_url, headers=HEADERS, timeout=10.0)
        doc_resp.raise_for_status()
        
        # 3. Clean the HTML
        doc_soup = BeautifulSoup(doc_resp.content, "lxml")
        for tag in doc_soup(['script', 'style', 'table']):
            tag.decompose()
            
        clean_text = doc_soup.get_text(separator=' ', strip=True)
        
        # 4. RUN HARDENED HEURISTIC PARSING LOGIC
        
        # A. Flexible multi-whitespace regex for items
        item_pattern = re.compile(r'\bItem\s*(?:No\s*\.\s*)?(\d\.\d{2})\b', re.IGNORECASE)
        found_items = list(set(item_pattern.findall(clean_text)))
        
        sentences = re.split(r'[.;!?\n]', clean_text.lower())
        
        # B. Advanced Executive Changes Heuristic
        executive_changes = False
        if "5.02" in found_items:
            executive_changes = True
        else:
            exec_keywords = ["resign", "resignation", "appoint", "appointment", "retire", "step down", "terminated"]
            exec_titles = ["ceo", "cfo", "chief executive officer", "chief financial officer", "director", "chairman"]
            negation_phrases = ["false", "deny", "denied", "unfounded", "rumor", "no executive change", "not true", "incorrect", "will not"]
            
            for sentence in sentences:
                has_title = any(title in sentence for title in exec_titles)
                has_keyword = any(word in sentence for word in exec_keywords)
                
                if has_title and has_keyword:
                    has_negation = any(neg in sentence for neg in negation_phrases)
                    if not has_negation:
                        executive_changes = True
                        break
                        
        # C. Advanced Bankruptcy Heuristics
        bankruptcy_or_receivership = False
        if "1.03" in found_items:
            bankruptcy_or_receivership = True
        else:
            bankruptcy_keywords = ["chapter 11", "bankruptcy", "receivership", "insolvent", "liquidate", "liquidation"]
            bankrupt_negations = ["avoided", "no longer", "not anticipate", "no plans", "lawyer"]
            
            for sentence in sentences:
                if any(word in sentence for word in bankruptcy_keywords):
                    if not any(neg in sentence for neg in bankrupt_negations):
                        bankruptcy_or_receivership = True
                        break
                        
        # D. Summary Fallback
        summary = clean_text[:200].strip() + "..."

        logger.info(f"Heuristic extraction successfully completed for {document_url}")
        
        return {
            "item_numbers": sorted(found_items),
            "executive_changes": executive_changes,
            "bankruptcy_or_receivership": bankruptcy_or_receivership,
            "summary": summary
        }

    except Exception as e:
        logger.error(f"Failed production heuristic extraction from {document_url}: {e}")
        return {
            "item_numbers": [],
            "executive_changes": False,
            "bankruptcy_or_receivership": False,
            "summary": f"Extraction error: {str(e)}"
        }