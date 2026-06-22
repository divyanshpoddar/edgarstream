"""
Schema drift detector for XBRL taxonomy changes.

EDGAR filers occasionally rename or deprecate US-GAAP concepts — e.g., migrating
from `Revenues` to `RevenueFromContractWithCustomerExcludingAssessedTax`. This
module compares each extraction result against the known expected schema and fires
structured alerts when required fields are absent or suspiciously zero.

Every drift event is:
  1. Logged at WARNING level with a JSON payload (grep-able in any log sink)
  2. Counted in Prometheus  →  `edgar_schema_drift_total{form_type, missing_field}`
  3. Persisted to `schema_drift_alerts` in PostgreSQL for trend analysis
"""
import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime

from shared.metrics import schema_drift_total

logger = logging.getLogger(__name__)


# ── Expected schemas ──────────────────────────────────────────────────────────

_EXPECTED: dict[str, set[str]] = {
    "10-K":    {"Assets", "Liabilities", "Revenues", "NetIncomeLoss"},
    "10-Q":    {"Assets", "Liabilities", "Revenues", "NetIncomeLoss"},
    "13F-HR":  {"issuer", "cusip", "value_usd_thousands", "shares"},
    "13F-HR/A": {"issuer", "cusip", "value_usd_thousands", "shares"},
}

# Fields that are sometimes legitimately zero for a filer; suppress zero-value
# alerts for these so we only alert on genuinely missing data.
_SOFT: dict[str, set[str]] = {
    "10-K": {"Liabilities"},
    "10-Q": {"Liabilities"},
}


# ── Drift event dataclass ─────────────────────────────────────────────────────

@dataclass
class DriftEvent:
    form_type: str
    accession_number: str
    company_name: str
    filing_url: str
    missing_fields: list[str]
    zero_value_fields: list[str]
    detected_at: str = field(
        default_factory=lambda: datetime.now(UTC).isoformat()
    )

    def as_dict(self) -> dict:
        return asdict(self)


# ── Checkers ──────────────────────────────────────────────────────────────────

def check_financials_drift(
    form_type: str,
    accession_number: str,
    company_name: str,
    filing_url: str,
    extracted: dict,
) -> DriftEvent | None:
    """Check a 10-K / 10-Q extraction dict for missing or zero-valued fields."""
    expected = _EXPECTED.get(form_type, set())
    soft = _SOFT.get(form_type, set())

    missing, zeroed = [], []
    for f in expected:
        val = extracted.get(f)
        if val is None:
            missing.append(f)
        elif val == 0 and f not in soft:
            zeroed.append(f)

    if not missing and not zeroed:
        return None

    return DriftEvent(
        form_type=form_type,
        accession_number=accession_number,
        company_name=company_name,
        filing_url=filing_url,
        missing_fields=missing,
        zero_value_fields=zeroed,
    )


def check_holdings_drift(
    form_type: str,
    accession_number: str,
    company_name: str,
    filing_url: str,
    holdings: list[dict],
) -> DriftEvent | None:
    """Check a 13F extraction result for an empty list or missing holding keys."""
    if not holdings:
        return DriftEvent(
            form_type=form_type,
            accession_number=accession_number,
            company_name=company_name,
            filing_url=filing_url,
            missing_fields=["holdings_list_empty"],
            zero_value_fields=[],
        )

    expected_keys = _EXPECTED.get(form_type, set())
    missing_keys = [k for k in expected_keys if k not in holdings[0]]
    if not missing_keys:
        return None

    return DriftEvent(
        form_type=form_type,
        accession_number=accession_number,
        company_name=company_name,
        filing_url=filing_url,
        missing_fields=missing_keys,
        zero_value_fields=[],
    )


# ── Emitter ───────────────────────────────────────────────────────────────────

def emit_drift_alert(event: DriftEvent) -> None:
    """Emit drift event to logs, Prometheus, and PostgreSQL (best-effort)."""

    logger.warning("SCHEMA_DRIFT %s", json.dumps(event.as_dict()))

    for f in event.missing_fields:
        schema_drift_total.labels(
            form_type=event.form_type, missing_field=f
        ).inc()
    for f in event.zero_value_fields:
        schema_drift_total.labels(
            form_type=event.form_type, missing_field=f"zero:{f}"
        ).inc()

    # PostgreSQL persistence is best-effort — a DB hiccup must not crash the pipeline
    try:
        from shared.utils.db import SessionLocal, SchemaDriftAlert  # noqa: PLC0415

        db = SessionLocal()
        try:
            db.add(
                SchemaDriftAlert(
                    accession_number=event.accession_number,
                    company_name=event.company_name,
                    form_type=event.form_type,
                    filing_url=event.filing_url,
                    missing_fields=json.dumps(event.missing_fields),
                    zero_value_fields=json.dumps(event.zero_value_fields),
                )
            )
            db.commit()
        finally:
            db.close()
    except Exception as exc:
        logger.error("Could not persist schema drift alert to DB: %s", exc)
