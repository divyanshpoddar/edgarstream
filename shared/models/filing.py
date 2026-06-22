# shared/models/filing.py
from datetime import datetime
from pydantic import BaseModel, Field, HttpUrl

class SECFilingMetadata(BaseModel):
    """
    The initial metadata extracted from the SEC EDGAR RSS feed.
    """
    accession_number: str = Field(..., description="Unique SEC filing identifier (e.g., 0001193125-24-123456)")
    cik: str = Field(..., description="Central Index Key of the filer")
    company_name: str
    form_type: str = Field(..., description="e.g., 10-K, 8-K, 13F-HR")
    filing_date: datetime
    document_url: HttpUrl = Field(..., description="Link to the index.htm of the filing")
    
    # Optional fields populated later in the pipeline
    is_processed: bool = False
    processing_latency_ms: int | None = None

class ParsedFilingData(BaseModel):
    """
    The structured data extracted from the filing, ready for Snowflake.
    """
    accession_number: str
    form_type: str
    extracted_data: dict = Field(default_factory=dict, description="JSON payload of extracted financials/holdings/events")
    extraction_success: bool
    error_log: str | None = None