"""
Prefect orchestration layer for the EdgarStream pipeline.

Architecture:
  drain_queue_flow  -- scheduled every 60 s; pops up to 50 items from Redis
    └─ process_filing_flow  -- one subflow per filing
         ├─ extract_*_task  -- retries on network / parsing failures
         ├─ persist_financials_task
         └─ persist_filing_log_task

Run locally (blocking serve loop):
    python services/workers/prefect_flow.py

Deploy to Prefect Cloud / self-hosted server:
    prefect deploy --all
"""
import os
import json
import time

from prefect import flow, task, get_run_logger
from redis import Redis

from shared.utils.db import SessionLocal, OperationalFilingLog, FinancialStatement, init_db
from shared.models.filing import SECFilingMetadata
from shared.metrics import (
    filings_processed_total,
    extraction_latency_seconds,
    fields_extracted_total,
    queue_depth,
)
from services.parser.form_10k import extract_10k_financials
from services.parser.form_10q import extract_10q_financials
from services.parser.form_13f import extract_13f_holdings
from services.parser.form_8k import extract_8k_events
from services.parser.form_s1 import extract_s1_data
from services.monitor.schema_drift import (
    check_financials_drift,
    check_holdings_drift,
    emit_drift_alert,
)

redis_client = Redis(
    host=os.getenv("REDIS_HOST", "localhost"),
    port=int(os.getenv("REDIS_PORT", 6379)),
    db=0,
    decode_responses=True,
)
FILING_QUEUE = "edgarstream:filing_queue"


# ── Extraction tasks (retries handle transient SEC network errors) ────────────

@task(name="extract-10k", retries=3, retry_delay_seconds=[30, 60, 120])
def extract_10k_task(index_url: str) -> dict:
    return extract_10k_financials(index_url)


@task(name="extract-10q", retries=3, retry_delay_seconds=[30, 60, 120])
def extract_10q_task(index_url: str) -> dict:
    return extract_10q_financials(index_url)


@task(name="extract-13f", retries=2, retry_delay_seconds=[15, 30])
def extract_13f_task(index_url: str) -> list:
    return extract_13f_holdings(index_url)


@task(name="extract-8k", retries=2, retry_delay_seconds=[15, 30])
def extract_8k_task(index_url: str) -> dict:
    return extract_8k_events(index_url)


# ── Persistence tasks ─────────────────────────────────────────────────────────

@task(name="persist-financials")
def persist_financials_task(meta: SECFilingMetadata, financials: dict) -> None:
    db = SessionLocal()
    try:
        row = FinancialStatement(
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
        db.merge(row)
        db.commit()
    finally:
        db.close()


@task(name="persist-log")
def persist_log_task(
    meta: SECFilingMetadata,
    status: str,
    latency_ms: int | None = None,
    error: str | None = None,
    success: bool = False,
) -> None:
    db = SessionLocal()
    try:
        log = db.query(OperationalFilingLog).filter_by(
            accession_number=meta.accession_number
        ).first()
        if not log:
            log = OperationalFilingLog(
                accession_number=meta.accession_number,
                cik=meta.cik,
                company_name=meta.company_name,
                form_type=meta.form_type,
                filing_date=meta.filing_date,
                download_url=str(meta.document_url),
            )
            db.add(log)
        log.status = status
        log.latency_ms = latency_ms
        log.extraction_success = success
        log.error_message = error
        db.commit()
    finally:
        db.close()


# ── Per-filing subflow ────────────────────────────────────────────────────────

@flow(name="process-filing", log_prints=True)
def process_filing_flow(metadata_dict: dict) -> None:
    logger = get_run_logger()
    start = time.time()
    meta = SECFilingMetadata(**metadata_dict)

    persist_log_task(meta, status="PROCESSING")

    try:
        extracted_data: dict = {}

        if meta.form_type == "10-K":
            financials = extract_10k_task(str(meta.document_url))
            extracted_data["financials"] = financials
            persist_financials_task(meta, financials)
            drift = check_financials_drift(
                meta.form_type, meta.accession_number, meta.company_name,
                str(meta.document_url), financials,
            )
            if drift:
                emit_drift_alert(drift)

        elif meta.form_type == "10-Q":
            financials = extract_10q_task(str(meta.document_url))
            extracted_data["financials"] = financials
            persist_financials_task(meta, financials)
            drift = check_financials_drift(
                meta.form_type, meta.accession_number, meta.company_name,
                str(meta.document_url), financials,
            )
            if drift:
                emit_drift_alert(drift)

        elif meta.form_type == "8-K":
            events = extract_8k_task(str(meta.document_url))
            extracted_data["events"] = events

        elif meta.form_type in ("S-1", "S-1/A"):
            s1_data = extract_s1_data(str(meta.document_url))
            extracted_data["s1"] = s1_data

        elif "13F" in meta.form_type:
            holdings = extract_13f_task(str(meta.document_url))
            extracted_data["holdings"] = holdings
            drift = check_holdings_drift(
                meta.form_type, meta.accession_number, meta.company_name,
                str(meta.document_url), holdings,
            )
            if drift:
                emit_drift_alert(drift)

        latency_ms = int((time.time() - start) * 1000)
        persist_log_task(meta, status="COMPLETED", latency_ms=latency_ms, success=True)

        filings_processed_total.labels(form_type=meta.form_type, status="completed").inc()
        extraction_latency_seconds.labels(form_type=meta.form_type).observe(
            time.time() - start
        )
        fields_extracted_total.labels(form_type=meta.form_type).inc(len(extracted_data))

        logger.info(f"Completed {meta.accession_number} ({meta.form_type}) in {latency_ms}ms")

    except Exception as e:
        persist_log_task(meta, status="FAILED", error=str(e))
        filings_processed_total.labels(form_type=meta.form_type, status="failed").inc()
        logger.error(f"Failed {meta.accession_number}: {e}")
        raise


# ── Top-level scheduled flow ──────────────────────────────────────────────────

@flow(name="edgar-queue-drain", log_prints=True)
def drain_queue_flow(batch_size: int = 50) -> int:
    """
    Drain up to `batch_size` filings from the Redis queue.
    Each item is processed as a subflow so Prefect tracks it individually.
    Scheduled to run every 60 seconds via the deployment below.
    """
    logger = get_run_logger()
    processed = 0

    for _ in range(batch_size):
        payload = redis_client.rpop(FILING_QUEUE)
        if not payload:
            break
        try:
            process_filing_flow(json.loads(payload))
            processed += 1
        except Exception as e:
            logger.error(f"Dispatch error: {e}")

    remaining = redis_client.llen(FILING_QUEUE)
    queue_depth.set(remaining)
    logger.info(f"Drained {processed} filings; {remaining} remaining in queue")
    return processed


if __name__ == "__main__":
    init_db()
    # `serve` blocks and re-runs the flow on the given interval.
    # Switch to `prefect deploy --all` for a production deployment.
    drain_queue_flow.serve(
        name="edgar-queue-drain-local",
        interval=60,
    )
