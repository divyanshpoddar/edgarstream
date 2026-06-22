export interface Filing {
  accession_number: string;
  company_name: string;
  form_type: string;
  filing_date: string;
  latency_ms: number | null;
  document_url: string;
}

export interface FinancialStatement {
  accession_number: string;
  company_name: string;
  cik: string;
  form_type: string | null;
  filing_date: string;
  total_assets: number | null;
  total_liabilities: number | null;
  revenues: number | null;
  net_income: number | null;
  source_xbrl_url: string | null;
  tag_provenance: Record<string, string>;
  extracted_at: string;
}

export interface DriftAlert {
  accession_number: string;
  company_name: string;
  form_type: string;
  missing_fields: string;
  zero_value_fields: string;
  detected_at: string;
}

export interface PipelineMetrics {
  timeframe: string;
  total_filings_ingested: number;
  pipeline_health: {
    average_latency_ms: number;
    max_latency_ms: number;
    extraction_success_rate: string;
  };
}

export interface VolumePoint {
  date: string;
  form_type: string;
  count: number;
}
