# services/warehouse/snowflake_sync.py
import logging
import pandas as pd
from sqlalchemy import create_engine
import snowflake.connector
from snowflake.connector.pandas_tools import write_pandas

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- CREDENTIALS ---
# Local Postgres (Where your operational data lives)
POSTGRES_URI = "postgresql://edgar_user:edgar_password@localhost:5434/edgar_metadata"

# Snowflake (Where your analytics data is going)
# Replace these with your actual Snowflake trial credentials
SNOWFLAKE_CREDS = {
    "user": "DIVYANSHPODDAR",
    "password": "Mylife@100times",
    "account": "USB09882", # e.g., 'xy12345.us-east-2.aws'
    "warehouse": "COMPUTE_WH",
    "database": "EDGAR_ANALYTICS",
    "schema": "PUBLIC"
}

def sync_postgres_to_snowflake():
    """
    Extracts financial statement data from local operational Postgres 
    and bulk-loads it into the Snowflake analytical data warehouse.
    """
    try:
        # 1. EXTRACT: Read from Postgres into a Pandas DataFrame
        logger.info("Extracting data from operational PostgreSQL...")
        pg_engine = create_engine(POSTGRES_URI)
        
        # We grab the 10-K data you parsed earlier
        query = "SELECT * FROM financial_statements;"
        df = pd.read_sql(query, pg_engine)
        
        if df.empty:
            logger.warning("No data found in Postgres to sync.")
            return

        # Snowflake requires column names to be strictly UPPERCASE
        df.columns = [col.upper() for col in df.columns]

        # write_pandas serialises datetime64 as integer nanoseconds which
        # Snowflake TIMESTAMP_NTZ rejects. Cast to ISO-8601 strings instead;
        # Snowflake auto-casts VARCHAR -> TIMESTAMP_NTZ during COPY INTO.
        for col in ["FILING_DATE", "EXTRACTED_AT"]:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], utc=True).dt.strftime("%Y-%m-%d %H:%M:%S")

        logger.info(f"Extracted {len(df)} rows. Preparing Snowflake load...")

        # 2. CONNECT: Establish Snowflake connection
        conn = snowflake.connector.connect(**SNOWFLAKE_CREDS)
        
        # Ensure the destination table exists
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS FINANCIAL_STATEMENTS (
            ACCESSION_NUMBER VARCHAR(50) PRIMARY KEY,
            COMPANY_NAME VARCHAR(255),
            CIK VARCHAR(20),
            FILING_DATE TIMESTAMP_NTZ,
            TOTAL_ASSETS BIGINT,
            TOTAL_LIABILITIES BIGINT,
            REVENUES BIGINT,
            NET_INCOME BIGINT,
            SOURCE_XBRL_URL VARCHAR(500),
            EXTRACTED_AT TIMESTAMP_NTZ
        )
        """
        conn.cursor().execute(create_table_sql)

        # 3. LOAD: Bulk write the Pandas DataFrame to Snowflake
        logger.info("Bulk-loading data into Snowflake...")
        success, num_chunks, num_rows, output = write_pandas(
            conn=conn,
            df=df,
            table_name="FINANCIAL_STATEMENTS",
            auto_create_table=False,
            overwrite=True # In production, you'd use 'upsert' or 'append'
        )

        if success:
            logger.info(f"🚀 SUCCESS! {num_rows} rows synced to Snowflake data warehouse.")
        else:
            logger.error("Failed to write to Snowflake.")

    except Exception as e:
        logger.error(f"Sync failed: {e}")
    finally:
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    print("=" * 60)
    print("   INITIATING SNOWFLAKE ELT WAREHOUSE SYNC")
    print("=" * 60)
    sync_postgres_to_snowflake()