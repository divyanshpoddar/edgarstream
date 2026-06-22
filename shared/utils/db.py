# shared/utils/db.py
import os
from sqlalchemy import create_engine, Column, String, DateTime, Boolean, Integer, BigInteger, Text
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+psycopg2://edgar_user:edgar_password@127.0.0.1:5434/edgar_metadata")

_is_sqlite = DATABASE_URL.startswith("sqlite")
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=not _is_sqlite,
    connect_args={} if _is_sqlite else {"connect_timeout": 10},
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class OperationalFilingLog(Base):
    __tablename__ = "filing_execution_logs"

    accession_number = Column(String, primary_key=True, index=True)
    cik = Column(String, index=True, nullable=False)
    company_name = Column(String, nullable=False)
    form_type = Column(String, index=True, nullable=False)
    filing_date = Column(DateTime, nullable=False)
    download_url = Column(String, nullable=False)
    
    # Process management tracking
    status = Column(String, default="QUEUED", index=True) # QUEUED, PROCESSING, COMPLETED, FAILED
    extraction_success = Column(Boolean, default=False)
    latency_ms = Column(Integer, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class FinancialStatement(Base):
    __tablename__ = "financial_statements"

    accession_number = Column(String(50), primary_key=True)
    company_name = Column(String(255), nullable=False)
    cik = Column(String(20), nullable=False, index=True)
    filing_date = Column(DateTime, nullable=False)
    total_assets = Column(BigInteger, nullable=True)
    total_liabilities = Column(BigInteger, nullable=True)
    revenues = Column(BigInteger, nullable=True)
    net_income = Column(BigInteger, nullable=True)
    form_type = Column(String(10), nullable=True, index=True)
    source_xbrl_url = Column(String(500), nullable=True)
    tag_provenance = Column(Text, nullable=True)   # JSON: {metric -> xbrl_concept_tag}
    extracted_at = Column(DateTime, default=datetime.utcnow)


class SchemaDriftAlert(Base):
    __tablename__ = "schema_drift_alerts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    accession_number = Column(String(50), nullable=False, index=True)
    company_name = Column(String(255), nullable=False)
    form_type = Column(String(20), nullable=False, index=True)
    filing_url = Column(String(500), nullable=True)
    missing_fields = Column(Text, nullable=False)       # JSON list
    zero_value_fields = Column(Text, nullable=False)    # JSON list
    detected_at = Column(DateTime, default=datetime.utcnow)


def init_db():
    Base.metadata.create_all(bind=engine)
