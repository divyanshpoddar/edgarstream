# services/api/main.py
import json
from fastapi import FastAPI, Depends, Query
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import func, cast, Date
from datetime import datetime, timedelta
from typing import Optional
from prometheus_fastapi_instrumentator import Instrumentator

from shared.utils.db import SessionLocal, OperationalFilingLog, FinancialStatement, SchemaDriftAlert

app = FastAPI(
    title="EdgarStream API",
    description="Real-time SEC EDGAR pipeline metrics and structured extraction.",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

Instrumentator().instrument(app).expose(app)

# Dependency to get DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.get("/")
def health_check():
    return {"status": "EdgarStream API is live"}

@app.get("/api/filings")
def get_recent_filings(
    form: Optional[str] = Query(default=None, description="Form type filter e.g. 8-K, 10-K, 13F-HR"),
    since: Optional[datetime] = Query(default=None, description="ISO date filter e.g. 2026-01-01"),
    limit: int = Query(default=20, le=100),
    db: Session = Depends(get_db)
):
    """Fetch the most recently processed SEC filings."""
    query = db.query(OperationalFilingLog).filter(OperationalFilingLog.status == "COMPLETED")

    if form:
        query = query.filter(OperationalFilingLog.form_type == form)
    if since:
        query = query.filter(OperationalFilingLog.filing_date >= since)

    filings = query.order_by(OperationalFilingLog.filing_date.desc()).limit(limit).all()
    
    return {
        "count": len(filings),
        "data": [
            {
                "accession_number": f.accession_number,
                "company_name": f.company_name,
                "form_type": f.form_type,
                "latency_ms": f.latency_ms,
                "filing_date": f.filing_date,
                "document_url": f.download_url
            } for f in filings
        ]
    }

@app.get("/api/drift")
def get_drift_alerts(
    form: Optional[str] = Query(default=None),
    limit: int = Query(default=20, le=100),
    db: Session = Depends(get_db),
):
    """Recent schema drift alerts — fires when expected XBRL tags go missing."""
    query = db.query(SchemaDriftAlert).order_by(SchemaDriftAlert.detected_at.desc())
    if form:
        query = query.filter(SchemaDriftAlert.form_type == form)
    alerts = query.limit(limit).all()
    return {
        "count": len(alerts),
        "data": [
            {
                "accession_number": a.accession_number,
                "company_name": a.company_name,
                "form_type": a.form_type,
                "missing_fields": a.missing_fields,
                "zero_value_fields": a.zero_value_fields,
                "detected_at": a.detected_at,
            }
            for a in alerts
        ],
    }


@app.get("/status", response_class=HTMLResponse)
def status_page():
    """Human-readable pipeline status dashboard."""
    return HTMLResponse(content=_STATUS_HTML)


@app.get("/api/metrics")
def get_pipeline_metrics(db: Session = Depends(get_db)):
    """The 'Killer Artifact' metrics for the dashboard."""
    last_24h = datetime.utcnow() - timedelta(hours=24)
    
    # Total filings in last 24h
    total_24h = db.query(OperationalFilingLog).filter(
        OperationalFilingLog.filing_date >= last_24h
    ).count()
    
    # Calculate Latency averages
    latency_stats = db.query(
        func.avg(OperationalFilingLog.latency_ms).label('avg_latency'),
        func.max(OperationalFilingLog.latency_ms).label('max_latency')
    ).filter(
        OperationalFilingLog.status == "COMPLETED"
    ).first()
    
    # Extraction Success Rate
    success_count = db.query(OperationalFilingLog).filter(
        OperationalFilingLog.extraction_success == True
    ).count()
    total_count = db.query(OperationalFilingLog).count()
    
    success_rate = (success_count / total_count * 100) if total_count > 0 else 0
    
    return {
        "timeframe": "Last 24 Hours",
        "total_filings_ingested": total_24h,
        "pipeline_health": {
            "average_latency_ms": int(latency_stats.avg_latency) if latency_stats.avg_latency else 0,
            "max_latency_ms": int(latency_stats.max_latency) if latency_stats.max_latency else 0,
            "extraction_success_rate": f"{success_rate:.1f}%"
        }
    }


@app.get("/api/financials")
def get_financials(
    company: Optional[str] = Query(default=None, description="Company name substring search"),
    form_type: Optional[str] = Query(default=None),
    limit: int = Query(default=20, le=100),
    db: Session = Depends(get_db),
):
    """Extracted financial statements with XBRL tag provenance."""
    query = db.query(FinancialStatement)
    if company:
        query = query.filter(FinancialStatement.company_name.ilike(f"%{company}%"))
    if form_type:
        query = query.filter(FinancialStatement.form_type == form_type)
    rows = query.order_by(FinancialStatement.extracted_at.desc()).limit(limit).all()
    return {
        "count": len(rows),
        "data": [
            {
                "accession_number": r.accession_number,
                "company_name": r.company_name,
                "cik": r.cik,
                "form_type": r.form_type,
                "filing_date": r.filing_date,
                "total_assets": r.total_assets,
                "total_liabilities": r.total_liabilities,
                "revenues": r.revenues,
                "net_income": r.net_income,
                "source_xbrl_url": r.source_xbrl_url,
                "tag_provenance": json.loads(r.tag_provenance) if r.tag_provenance else {},
                "extracted_at": r.extracted_at,
            }
            for r in rows
        ],
    }


@app.get("/api/volume")
def get_volume(
    days: int = Query(default=7, le=30),
    db: Session = Depends(get_db),
):
    """Daily filing counts by form type for the last N days — used by the volume chart."""
    since = datetime.utcnow() - timedelta(days=days)
    results = (
        db.query(
            cast(OperationalFilingLog.filing_date, Date).label("date"),
            OperationalFilingLog.form_type,
            func.count().label("count"),
        )
        .filter(
            OperationalFilingLog.filing_date >= since,
            OperationalFilingLog.status == "COMPLETED",
        )
        .group_by(
            cast(OperationalFilingLog.filing_date, Date),
            OperationalFilingLog.form_type,
        )
        .order_by(cast(OperationalFilingLog.filing_date, Date))
        .all()
    )
    return {
        "days": days,
        "data": [
            {"date": str(r.date), "form_type": r.form_type, "count": r.count}
            for r in results
        ],
    }


_STATUS_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>EdgarStream — Pipeline Status</title>
  <style>
    :root {
      --bg: #0d1117; --surface: #161b22; --border: #30363d;
      --text: #e6edf3; --muted: #8b949e; --green: #3fb950;
      --yellow: #d29922; --red: #f85149; --blue: #58a6ff;
      --purple: #bc8cff; --orange: #ffa657;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { background: var(--bg); color: var(--text); font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", monospace; font-size: 14px; }
    header { background: var(--surface); border-bottom: 1px solid var(--border); padding: 16px 32px; display: flex; align-items: center; justify-content: space-between; }
    .logo { font-size: 20px; font-weight: 700; letter-spacing: -0.5px; }
    .logo span { color: var(--blue); }
    .live-badge { display: flex; align-items: center; gap: 6px; font-size: 12px; color: var(--green); }
    .pulse { width: 8px; height: 8px; border-radius: 50%; background: var(--green); animation: pulse 2s infinite; }
    @keyframes pulse { 0%,100%{opacity:1;transform:scale(1)} 50%{opacity:.5;transform:scale(1.3)} }
    main { max-width: 1200px; margin: 0 auto; padding: 32px; }
    h2 { font-size: 13px; font-weight: 600; color: var(--muted); text-transform: uppercase; letter-spacing: 1px; margin-bottom: 16px; }
    .metrics-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px; margin-bottom: 40px; }
    .metric-card { background: var(--surface); border: 1px solid var(--border); border-radius: 8px; padding: 20px; }
    .metric-label { font-size: 12px; color: var(--muted); margin-bottom: 8px; }
    .metric-value { font-size: 32px; font-weight: 700; line-height: 1; }
    .metric-sub { font-size: 12px; color: var(--muted); margin-top: 6px; }
    .green { color: var(--green); } .blue { color: var(--blue); } .orange { color: var(--orange); } .purple { color: var(--purple); }
    .section { margin-bottom: 40px; }
    .breakdown { display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 12px; margin-bottom: 40px; }
    .form-pill { background: var(--surface); border: 1px solid var(--border); border-radius: 6px; padding: 12px 16px; }
    .form-pill .form-name { font-weight: 600; margin-bottom: 4px; }
    .form-pill .form-count { font-size: 22px; font-weight: 700; color: var(--blue); }
    .form-pill .form-rate { font-size: 11px; color: var(--muted); margin-top: 2px; }
    table { width: 100%; border-collapse: collapse; background: var(--surface); border: 1px solid var(--border); border-radius: 8px; overflow: hidden; }
    th { background: #1c2128; color: var(--muted); font-size: 11px; text-transform: uppercase; letter-spacing: 0.8px; padding: 10px 16px; text-align: left; border-bottom: 1px solid var(--border); }
    td { padding: 10px 16px; border-bottom: 1px solid #21262d; font-size: 13px; }
    tr:last-child td { border-bottom: none; }
    tr:hover td { background: #1c2128; }
    .status-ok { color: var(--green); font-weight: 600; }
    .status-fail { color: var(--red); font-weight: 600; }
    .tag { display: inline-block; padding: 1px 8px; border-radius: 12px; font-size: 11px; font-weight: 600; }
    .tag-10k { background: #1f3a5c; color: var(--blue); }
    .tag-10q { background: #1a3a2a; color: var(--green); }
    .tag-13f { background: #3a2a1f; color: var(--orange); }
    .tag-8k  { background: #3a1f2a; color: var(--purple); }
    .tag-s1  { background: #2a1f3a; color: #bc8cff; }
    .tag-other { background: #2a2a2a; color: var(--muted); }
    .drift-row td { color: var(--yellow); }
    .error { color: var(--red); font-style: italic; }
    .loading { color: var(--muted); }
    footer { text-align: center; padding: 32px; color: var(--muted); font-size: 12px; border-top: 1px solid var(--border); margin-top: 40px; }
    a { color: var(--blue); text-decoration: none; } a:hover { text-decoration: underline; }
    .uptime-bar { height: 4px; background: var(--border); border-radius: 2px; margin-top: 8px; }
    .uptime-fill { height: 100%; background: var(--green); border-radius: 2px; transition: width 0.5s; }
  </style>
</head>
<body>
<header>
  <div class="logo">Edgar<span>Stream</span></div>
  <div class="live-badge"><div class="pulse"></div> Live · updates every 30s</div>
</header>
<main>
  <!-- KPI row -->
  <h2>Pipeline Overview · Last 24 Hours</h2>
  <div class="metrics-grid" id="kpi-grid">
    <div class="metric-card"><div class="metric-label">Filings Ingested</div><div class="metric-value green" id="kpi-total">—</div><div class="metric-sub">24-hour window</div></div>
    <div class="metric-card"><div class="metric-label">Avg Latency</div><div class="metric-value blue" id="kpi-avg-lat">—</div><div class="metric-sub">end-to-end (ms)</div></div>
    <div class="metric-card"><div class="metric-label">Max Latency</div><div class="metric-value orange" id="kpi-max-lat">—</div><div class="metric-sub">worst case (ms)</div></div>
    <div class="metric-card"><div class="metric-label">Success Rate</div><div class="metric-value purple" id="kpi-success">—</div><div class="metric-sub">extraction accuracy</div></div>
    <div class="metric-card"><div class="metric-label">Drift Alerts</div><div class="metric-value" id="kpi-drift" style="color:var(--yellow)">—</div><div class="metric-sub">schema changes detected</div></div>
  </div>

  <!-- Form-type breakdown -->
  <div class="section">
    <h2>Breakdown by Form Type</h2>
    <div class="breakdown" id="form-breakdown">
      <div class="loading">Loading…</div>
    </div>
  </div>

  <!-- Recent filings table -->
  <div class="section">
    <h2>Recent Filings</h2>
    <table>
      <thead>
        <tr><th>Company</th><th>Form</th><th>Filed</th><th>Latency</th><th>Status</th></tr>
      </thead>
      <tbody id="filings-tbody"><tr><td colspan="5" class="loading">Loading…</td></tr></tbody>
    </table>
  </div>

  <!-- Drift alerts table -->
  <div class="section">
    <h2>Recent Schema Drift Alerts</h2>
    <table>
      <thead>
        <tr><th>Company</th><th>Form</th><th>Missing Fields</th><th>Detected</th></tr>
      </thead>
      <tbody id="drift-tbody"><tr><td colspan="4" class="loading">Loading…</td></tr></tbody>
    </table>
  </div>
</main>
<footer>
  EdgarStream — real-time SEC EDGAR pipeline &nbsp;·&nbsp;
  <a href="/docs">API docs</a> &nbsp;·&nbsp;
  <a href="/api/filings">JSON feed</a> &nbsp;·&nbsp;
  <a href="/api/metrics">Metrics</a>
</footer>
<script>
const FORM_COLORS = {'10-K':'tag-10k','10-Q':'tag-10q','13F-HR':'tag-13f','13F-NT':'tag-13f','8-K':'tag-8k','S-1':'tag-s1','S-1/A':'tag-s1'};
function tagClass(f){return FORM_COLORS[f]||'tag-other';}
function fmt(dt){if(!dt)return '—';const d=new Date(dt);return d.toLocaleDateString('en-US',{month:'short',day:'numeric',hour:'2-digit',minute:'2-digit'});}
function fmtLat(ms){if(ms==null)return '—';return ms>1000?(ms/1000).toFixed(1)+'s':ms+'ms';}

async function loadMetrics(){
  try{
    const r=await fetch('/api/metrics');
    const d=await r.json();
    document.getElementById('kpi-total').textContent=d.total_filings_ingested??'0';
    document.getElementById('kpi-avg-lat').textContent=d.pipeline_health.average_latency_ms??'0';
    document.getElementById('kpi-max-lat').textContent=d.pipeline_health.max_latency_ms??'0';
    document.getElementById('kpi-success').textContent=d.pipeline_health.extraction_success_rate??'—';
  }catch(e){document.getElementById('kpi-total').textContent='err';}
}

async function loadDriftCount(){
  try{
    const r=await fetch('/api/drift?limit=100');
    const d=await r.json();
    document.getElementById('kpi-drift').textContent=d.count??'0';
  }catch(e){}
}

async function loadFilings(){
  try{
    const r=await fetch('/api/filings?limit=20');
    const d=await r.json();
    const rows=d.data||[];

    // breakdown
    const counts={};
    rows.forEach(f=>{counts[f.form_type]=(counts[f.form_type]||0)+1;});
    const bd=document.getElementById('form-breakdown');
    if(Object.keys(counts).length===0){
      bd.innerHTML='<div style="color:var(--muted)">No filings processed yet.</div>';
    }else{
      bd.innerHTML=Object.entries(counts).sort((a,b)=>b[1]-a[1]).map(([ft,c])=>
        `<div class="form-pill"><div class="form-name"><span class="tag ${tagClass(ft)}">${ft}</span></div><div class="form-count">${c}</div><div class="form-rate">filings</div></div>`
      ).join('');
    }

    // table
    const tbody=document.getElementById('filings-tbody');
    if(rows.length===0){
      tbody.innerHTML='<tr><td colspan="5" style="color:var(--muted);text-align:center">No filings processed yet — pipeline is listening.</td></tr>';
    }else{
      tbody.innerHTML=rows.map(f=>`
        <tr>
          <td>${f.company_name}</td>
          <td><span class="tag ${tagClass(f.form_type)}">${f.form_type}</span></td>
          <td>${fmt(f.filing_date)}</td>
          <td>${fmtLat(f.latency_ms)}</td>
          <td class="status-ok">✓ OK</td>
        </tr>`).join('');
    }
  }catch(e){
    document.getElementById('filings-tbody').innerHTML='<tr><td colspan="5" class="error">Failed to load — is the API running?</td></tr>';
  }
}

async function loadDrift(){
  try{
    const r=await fetch('/api/drift?limit=10');
    const d=await r.json();
    const tbody=document.getElementById('drift-tbody');
    if(!d.data||d.data.length===0){
      tbody.innerHTML='<tr><td colspan="4" style="color:var(--muted);text-align:center">No drift detected — all expected XBRL tags present.</td></tr>';
    }else{
      tbody.innerHTML=d.data.map(a=>`
        <tr class="drift-row">
          <td>${a.company_name}</td>
          <td><span class="tag ${tagClass(a.form_type)}">${a.form_type}</span></td>
          <td style="font-family:monospace;font-size:12px">${a.missing_fields}</td>
          <td>${fmt(a.detected_at)}</td>
        </tr>`).join('');
    }
  }catch(e){}
}

async function refresh(){
  await Promise.all([loadMetrics(),loadFilings(),loadDrift(),loadDriftCount()]);
}

refresh();
setInterval(refresh,30000);
</script>
</body>
</html>"""