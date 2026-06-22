import os
import logging
import snowflake.connector

logger = logging.getLogger(__name__)

_SNOWFLAKE_CREDS = {
    "user":      os.getenv("SNOWFLAKE_USER"),
    "password":  os.getenv("SNOWFLAKE_PASSWORD"),
    "account":   os.getenv("SNOWFLAKE_ACCOUNT"),
    "warehouse": os.getenv("SNOWFLAKE_WAREHOUSE", "COMPUTE_WH"),
    "database":  os.getenv("SNOWFLAKE_DATABASE", "EDGAR_ANALYTICS"),
    "schema":    os.getenv("SNOWFLAKE_SCHEMA", "PUBLIC"),
}

_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS FINANCIAL_STATEMENTS (
    ACCESSION_NUMBER  VARCHAR(50)   PRIMARY KEY,
    COMPANY_NAME      VARCHAR(255),
    CIK               VARCHAR(20),
    FORM_TYPE         VARCHAR(10),
    FILING_DATE       TIMESTAMP_NTZ,
    TOTAL_ASSETS      BIGINT,
    TOTAL_LIABILITIES BIGINT,
    REVENUES          BIGINT,
    NET_INCOME        BIGINT,
    SOURCE_XBRL_URL   VARCHAR(500),
    TAG_PROVENANCE    VARCHAR(4000),
    EXTRACTED_AT      TIMESTAMP_NTZ
)
"""

_UPSERT_SQL = """
MERGE INTO FINANCIAL_STATEMENTS tgt
USING (
    SELECT
        %(accession_number)s  AS ACCESSION_NUMBER,
        %(company_name)s      AS COMPANY_NAME,
        %(cik)s               AS CIK,
        %(form_type)s         AS FORM_TYPE,
        %(filing_date)s       AS FILING_DATE,
        %(total_assets)s      AS TOTAL_ASSETS,
        %(total_liabilities)s AS TOTAL_LIABILITIES,
        %(revenues)s          AS REVENUES,
        %(net_income)s        AS NET_INCOME,
        %(source_xbrl_url)s   AS SOURCE_XBRL_URL,
        %(tag_provenance)s    AS TAG_PROVENANCE,
        CURRENT_TIMESTAMP()   AS EXTRACTED_AT
) src ON tgt.ACCESSION_NUMBER = src.ACCESSION_NUMBER
WHEN MATCHED THEN UPDATE SET
    COMPANY_NAME = src.COMPANY_NAME, CIK = src.CIK, FORM_TYPE = src.FORM_TYPE,
    FILING_DATE = src.FILING_DATE, TOTAL_ASSETS = src.TOTAL_ASSETS,
    TOTAL_LIABILITIES = src.TOTAL_LIABILITIES, REVENUES = src.REVENUES,
    NET_INCOME = src.NET_INCOME, SOURCE_XBRL_URL = src.SOURCE_XBRL_URL,
    TAG_PROVENANCE = src.TAG_PROVENANCE, EXTRACTED_AT = src.EXTRACTED_AT
WHEN NOT MATCHED THEN INSERT (
    ACCESSION_NUMBER, COMPANY_NAME, CIK, FORM_TYPE, FILING_DATE,
    TOTAL_ASSETS, TOTAL_LIABILITIES, REVENUES, NET_INCOME,
    SOURCE_XBRL_URL, TAG_PROVENANCE, EXTRACTED_AT
) VALUES (
    src.ACCESSION_NUMBER, src.COMPANY_NAME, src.CIK, src.FORM_TYPE, src.FILING_DATE,
    src.TOTAL_ASSETS, src.TOTAL_LIABILITIES, src.REVENUES, src.NET_INCOME,
    src.SOURCE_XBRL_URL, src.TAG_PROVENANCE, src.EXTRACTED_AT
)
"""

def _snowflake_enabled() -> bool:
    return all([_SNOWFLAKE_CREDS["user"], _SNOWFLAKE_CREDS["password"], _SNOWFLAKE_CREDS["account"]])


def _get_conn():
    return snowflake.connector.connect(**{k: v for k, v in _SNOWFLAKE_CREDS.items() if v})


def ensure_schema():
    """Create the FINANCIAL_STATEMENTS table if it doesn't exist. Called once on worker startup."""
    if not _snowflake_enabled():
        logger.warning("Snowflake creds not set — skipping schema init")
        return
    try:
        conn = _get_conn()
        conn.cursor().execute(_CREATE_TABLE_SQL)
        conn.close()
        logger.info("Snowflake schema verified")
    except Exception as e:
        logger.error(f"Snowflake schema init failed: {e}")


def upsert_financial(row: dict):
    """Upsert a single financial statement row into Snowflake. Called per filing."""
    if not _snowflake_enabled():
        return
    try:
        conn = _get_conn()
        conn.cursor().execute(_UPSERT_SQL, {
            "accession_number":  row.get("accession_number"),
            "company_name":      row.get("company_name"),
            "cik":               row.get("cik"),
            "form_type":         row.get("form_type"),
            "filing_date":       str(row.get("filing_date", "")),
            "total_assets":      row.get("total_assets"),
            "total_liabilities": row.get("total_liabilities"),
            "revenues":          row.get("revenues"),
            "net_income":        row.get("net_income"),
            "source_xbrl_url":   row.get("source_xbrl_url"),
            "tag_provenance":    row.get("tag_provenance"),
        })
        conn.close()
        logger.info(f"Snowflake upsert OK: {row.get('accession_number')} ({row.get('company_name')})")
    except Exception as e:
        logger.error(f"Snowflake upsert failed for {row.get('accession_number')}: {e}")
