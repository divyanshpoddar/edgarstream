# shared/metrics.py
from prometheus_client import Counter, Histogram, Gauge

# Total filings processed, labelled by form type and final status
filings_processed_total = Counter(
    "edgar_filings_processed_total",
    "Total SEC filings processed by the pipeline",
    ["form_type", "status"],  # status: completed | failed
)

# Extraction latency histogram — lets Prometheus compute p50/p95/p99
extraction_latency_seconds = Histogram(
    "edgar_extraction_latency_seconds",
    "End-to-end extraction latency per filing",
    ["form_type"],
    buckets=[0.1, 0.5, 1, 2, 5, 10, 30, 60, 120],
)

# Running count of fields successfully extracted per form type
fields_extracted_total = Counter(
    "edgar_fields_extracted_total",
    "Number of structured fields successfully extracted",
    ["form_type"],
)

# Current queue depth (snapshot gauge, updated each worker loop tick)
queue_depth = Gauge(
    "edgar_queue_depth",
    "Number of filings currently waiting in the Redis queue",
)

# Schema drift events — fires when expected XBRL tags go missing from a filing
schema_drift_total = Counter(
    "edgar_schema_drift_total",
    "Number of schema drift events detected (missing or zero XBRL fields)",
    ["form_type", "missing_field"],
)
