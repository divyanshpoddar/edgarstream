# services/workers/pipeline_worker.py
import os
import json
import time
import logging
from redis import Redis
from prometheus_client import start_http_server

# Internal shared imports
from shared.utils.db import SessionLocal, OperationalFilingLog, FinancialStatement, init_db
from shared.models.filing import SECFilingMetadata
from shared.metrics import filings_processed_total, extraction_latency_seconds, fields_extracted_total, queue_depth

# Parsers
from services.parser.form_13f import extract_13f_holdings
from services.parser.form_8k import extract_8k_events
from services.parser.form_10k import extract_10k_financials
from services.parser.form_10q import extract_10q_financials
from services.parser.form_s1 import extract_s1_data

# Schema drift detection
from services.monitor.schema_drift import (
    check_financials_drift,
    check_holdings_drift,
    emit_drift_alert,
)
from services.warehouse.snowflake_sync import ensure_schema, upsert_financial

# Logging Configuration
logging.basicConfig(level=logging.INFO, format='%(asctime)s - [%(levelname)s] - %(message)s')
logger = logging.getLogger(__name__)

# Redis Connection (Ensure this matches your environment setup)
redis_client = Redis(
    host=os.getenv("REDIS_HOST", "localhost"),
    port=int(os.getenv("REDIS_PORT", 6379)),
    password=os.getenv("REDIS_PASSWORD", None),
    ssl=os.getenv("REDIS_SSL", "false").lower() == "true",
    db=0,
    decode_responses=True,
)
FILING_QUEUE = "edgarstream:filing_queue"

def process_filing(metadata_dict: dict):
    """Router & processing logic for individual filings."""
    start_time = time.time()
    
    # Validate the incoming payload against our Pydantic contract
    meta = SECFilingMetadata(**metadata_dict)
    
    db = SessionLocal()
    
    # 1. State Management: Check if log already exists, otherwise write state to Postgres
    db_log = db.query(OperationalFilingLog).filter_by(accession_number=meta.accession_number).first()
    if not db_log:
        db_log = OperationalFilingLog(
            accession_number=meta.accession_number,
            cik=meta.cik,
            company_name=meta.company_name,
            form_type=meta.form_type,
            filing_date=meta.filing_date,
            download_url=str(meta.document_url),
            status="PROCESSING"
        )
        db.add(db_log)
    else:
        db_log.status = "PROCESSING"
    db.commit()

    logger.info(f"Worker processing form {meta.form_type} for {meta.company_name}")
    
    try:
        # 2. --- PARSING STRATEGY ROUTER ---
        extracted_data = {}
        
        if meta.form_type == "10-K":
            logger.info(f"Triggering XBRL 10-K extraction for {meta.accession_number}")
            financials = extract_10k_financials(str(meta.document_url))
            extracted_data["financials"] = financials

            fin_row = FinancialStatement(
                accession_number=meta.accession_number,
                company_name=meta.company_name,
                cik=meta.cik,
                form_type=meta.form_type,
                filing_date=meta.filing_date,
                total_assets=financials.get("Assets"),
                total_liabilities=financials.get("Liabilities"),
                revenues=financials.get("Revenues"),
                net_income=financials.get("NetIncomeLoss"),
                source_xbrl_url=financials.get("source_xbrl_url"),
                tag_provenance=json.dumps(financials.get("tag_provenance", {})),
            )
            db.merge(fin_row)
            db.commit()
            logger.info(f"Persisted 10-K financials for {meta.company_name} ({meta.accession_number})")
            upsert_financial({
                "accession_number": meta.accession_number, "company_name": meta.company_name,
                "cik": meta.cik, "form_type": meta.form_type, "filing_date": meta.filing_date,
                "total_assets": financials.get("Assets"), "total_liabilities": financials.get("Liabilities"),
                "revenues": financials.get("Revenues"), "net_income": financials.get("NetIncomeLoss"),
                "source_xbrl_url": financials.get("source_xbrl_url"),
                "tag_provenance": json.dumps(financials.get("tag_provenance", {})),
            })

            drift = check_financials_drift(
                meta.form_type, meta.accession_number, meta.company_name,
                str(meta.document_url), financials,
            )
            if drift:
                emit_drift_alert(drift)

        elif meta.form_type == "10-Q":
            logger.info(f"Triggering XBRL 10-Q extraction for {meta.accession_number}")
            financials = extract_10q_financials(str(meta.document_url))
            extracted_data["financials"] = financials

            fin_row = FinancialStatement(
                accession_number=meta.accession_number,
                company_name=meta.company_name,
                cik=meta.cik,
                form_type=meta.form_type,
                filing_date=meta.filing_date,
                total_assets=financials.get("Assets"),
                total_liabilities=financials.get("Liabilities"),
                revenues=financials.get("Revenues"),
                net_income=financials.get("NetIncomeLoss"),
                source_xbrl_url=financials.get("source_xbrl_url"),
                tag_provenance=json.dumps(financials.get("tag_provenance", {})),
            )
            db.merge(fin_row)
            db.commit()
            logger.info(f"Persisted 10-Q financials for {meta.company_name}")
            upsert_financial({
                "accession_number": meta.accession_number, "company_name": meta.company_name,
                "cik": meta.cik, "form_type": meta.form_type, "filing_date": meta.filing_date,
                "total_assets": financials.get("Assets"), "total_liabilities": financials.get("Liabilities"),
                "revenues": financials.get("Revenues"), "net_income": financials.get("NetIncomeLoss"),
                "source_xbrl_url": financials.get("source_xbrl_url"),
                "tag_provenance": json.dumps(financials.get("tag_provenance", {})),
            })

            drift = check_financials_drift(
                meta.form_type, meta.accession_number, meta.company_name,
                str(meta.document_url), financials,
            )
            if drift:
                emit_drift_alert(drift)

        elif meta.form_type == "8-K":
            logger.info(f"Triggering AI 8-K extraction for {meta.accession_number}")
            events = extract_8k_events(str(meta.document_url))
            extracted_data["material_events"] = events
            logger.info(f"8-K Extracted Summary: {events.get('summary', 'None')}")

        elif meta.form_type in ("S-1", "S-1/A"):
            logger.info(f"Triggering S-1 extraction for {meta.accession_number}")
            s1_data = extract_s1_data(str(meta.document_url))
            extracted_data["s1"] = s1_data
            logger.info(
                f"S-1 extracted for {meta.company_name}: "
                f"price=${s1_data.get('offering_price_low')}-${s1_data.get('offering_price_high')}, "
                f"shares={s1_data.get('shares_offered')}"
            )

        elif "13F" in meta.form_type:
            logger.info(f"Triggering 13F extraction for {meta.accession_number}")
            holdings = extract_13f_holdings(str(meta.document_url))
            extracted_data["holdings"] = holdings
            extracted_data["total_positions"] = len(holdings)
            logger.info(f"Successfully extracted {len(holdings)} positions for {meta.company_name}")

            drift = check_holdings_drift(
                meta.form_type, meta.accession_number, meta.company_name,
                str(meta.document_url), holdings,
            )
            if drift:
                emit_drift_alert(drift)
            
        # 3. Complete transaction details
        end_time = time.time()
        latency = int((end_time - start_time) * 1000)
        latency_seconds = (end_time - start_time)

        db_log.status = "COMPLETED"
        db_log.extraction_success = True
        db_log.latency_ms = latency
        db.commit()

        # Prometheus metrics
        filings_processed_total.labels(form_type=meta.form_type, status="completed").inc()
        extraction_latency_seconds.labels(form_type=meta.form_type).observe(latency_seconds)
        fields_extracted_total.labels(form_type=meta.form_type).inc(len(extracted_data))

        logger.info(f"Successfully processed {meta.accession_number} in {latency}ms")

    except Exception as e:
        db_log.status = "FAILED"
        db_log.extraction_success = False
        db_log.error_message = str(e)
        db.commit()
        filings_processed_total.labels(form_type=meta.form_type, status="failed").inc()
        logger.error(f"Failed to process filing {meta.accession_number}: {e}")
    finally:
        db.close()


def start_worker():
    """Main worker daemon loop."""
    logger.info("Initializing Operational Database Tables...")
    init_db()
    ensure_schema()

    # Render sets PORT dynamically; fall back to METRICS_PORT for local/Railway
    metrics_port = int(os.getenv("PORT", os.getenv("METRICS_PORT", "9100")))
    start_http_server(metrics_port)
    logger.info(f"Prometheus metrics server started on port {metrics_port}")
    
    logger.info("Worker pool listening for real-time pipeline payloads...")
    while True:
        # RPOP blocks until something drops into the Redis queue list
        queue_depth.set(redis_client.llen(FILING_QUEUE))
        payload = redis_client.rpop(FILING_QUEUE)
        if not payload:
            time.sleep(1) # Sleep briefly if queue is temporarily drained to save CPU
            continue
            
        try:
            metadata_dict = json.loads(payload)
            process_filing(metadata_dict)
        except Exception as e:
            logger.critical(f"Pipeline panic on raw payload ingestion: {e}")

if __name__ == "__main__":
    start_worker()