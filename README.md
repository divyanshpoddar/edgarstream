# EdgarStream

[![CI](https://github.com/divyanshpoddar/edgarstream/actions/workflows/ci.yml/badge.svg)](https://github.com/divyanshpoddar/edgarstream/actions/workflows/ci.yml)

A production-grade real-time SEC EDGAR filings pipeline with structured extraction,
schema drift detection, and a live analytics dashboard.

**Live endpoints**

| Service | URL |
|---------|-----|
| API status dashboard | https://edgarstream-mrhv8m3tz-divyanshpoddars-projects.vercel.app/status |
| REST API | https://edgarstream-mrhv8m3tz-divyanshpoddars-projects.vercel.app/api/filings |
| Frontend | https://edgarstream-b3zw-gu0jxklja-divyanshpoddars-projects.vercel.app |
| Worker metrics | https://edgarstream-worker.onrender.com/metrics |

---

## What it does

```
SEC EDGAR RSS feed
      │  (every 30 min)
      ▼
 rss_poller.py  ──push──►  Upstash Redis queue  ──pop──►  pipeline_worker.py
                                                                    │
                              ┌─────────────────────────────────────┤
                              │  Form type router                   │
                              │  10-K / 10-Q  → Arelle XBRL        │
                              │  13F          → XML parser          │
                              │  8-K          → heuristic HTML      │
                              │  S-1 / S-1/A  → heuristic HTML      │
                              └──────────────┬──────────────────────┘
                                             │
                              ┌──────────────▼──────────────────────┐
                              │  Neon PostgreSQL  (operational DB)  │
                              │  Snowflake        (analytics DWH)   │
                              │  Prometheus metrics                 │
                              └──────────────────────────────────────┘
                                             │
                              ┌──────────────▼──────────────────────┐
                              │  FastAPI  (Vercel)                  │
                              │  Next.js dashboard  (Vercel)        │
                              └──────────────────────────────────────┘
```

---

## Key numbers

| Metric | Value |
|--------|-------|
| Poll interval | 30 min (SEC EDGAR fair-use) |
| Form types | 10-K, 10-Q, 8-K, 13F-HR, 13F-HR/A, S-1, S-1/A |
| Financial fields | Assets, Liabilities, Revenues, Net Income + XBRL tag provenance |
| Idempotency | Redis seen-set — same accession never processed twice |
| Snowflake sync | Per-filing MERGE upsert (real-time, not batch) |
| CI | GitHub Actions — 34 tests, ruff lint, ~2 min |

---

## Pipeline workers — two implementations

This project ships **two functionally equivalent workers**. One runs in production;
the other demonstrates Prefect orchestration for teams that already run a Prefect server.

### `services/workers/pipeline_worker.py` — production (Render)

Plain Python consumer loop. No orchestration dependency. Chosen for the free-tier
Render deployment because Prefect Cloud requires a server or paid agent.

```
while True:
    payload = redis.rpop(queue)
    process_filing(payload)   # extract → persist Neon → upsert Snowflake
```

Failures are caught, logged to `filing_execution_logs`, and surfaced via the
`/api/metrics` endpoint. Prometheus counters track success rate and latency.

### `services/workers/prefect_flow.py` — Prefect orchestration (local / Prefect Cloud)

Same extraction logic, but each parser call is a `@task` with automatic retries
and exponential back-off. Every filing becomes a trackable subflow in the Prefect UI.

| Task | Retries | Back-off |
|------|---------|----------|
| 10-K / 10-Q XBRL extraction | 3 | 30 s → 60 s → 120 s |
| 13F / 8-K extraction | 2 | 15 s → 30 s |
| DB persistence | 1 | — |

To run locally with the Prefect UI:
```bash
python services/workers/prefect_flow.py
# or deploy to Prefect Cloud:
prefect deploy --all
```

The bare worker was chosen for production to eliminate the Prefect server dependency
on free-tier infrastructure. In a bank environment with a managed Prefect or Airflow
server, `prefect_flow.py` is the right choice — it gives per-task observability,
retry auditability, and a UI for on-call engineers.

---

## Engineering signals

**Idempotency** — every accession number is hashed into a Redis seen-set before
queuing. Re-processing the same filing produces identical output and is a no-op
at the DB layer (`db.merge()` keyed on `accession_number`).

**XBRL tag provenance** — every extracted financial metric records which exact
XBRL concept produced it, e.g.:
```json
{"Revenues": "RevenueFromContractWithCustomerExcludingAssessedTax"}
```
Stored in the `tag_provenance` column and surfaced in the `/explore` dashboard.
Enables auditors to trace any number back to its source filing and taxonomy tag.

**Schema drift detection** — `services/monitor/schema_drift.py` runs after every
extraction and compares present XBRL concepts against the expected set. Missing or
zero-valued required fields generate a `schema_drift_alerts` row — so SEC taxonomy
changes (issued annually) are caught automatically.

**Reproducibility** — every row in `financial_statements` links to `source_xbrl_url`.
Any extracted number can be re-derived from the original SEC filing.

---

## API reference

| Endpoint | Description |
|----------|-------------|
| `GET /` | Health check |
| `GET /status` | HTML pipeline dashboard (auto-refreshes every 30 s) |
| `GET /api/filings` | Recent filings. Params: `form`, `limit` |
| `GET /api/financials` | XBRL financials + tag provenance. Params: `company`, `form_type` |
| `GET /api/metrics` | Pipeline KPIs: latency, success rate, 24 h ingestion count |
| `GET /api/volume` | Daily filing counts by form type. Param: `days` |
| `GET /api/drift` | Schema drift alerts. Param: `form` |
| `GET /docs` | Swagger UI |

---

## Tech stack

| Layer | Technology |
|-------|-----------|
| Language | Python 3.12 |
| API | FastAPI + Mangum (Vercel serverless) |
| Frontend | Next.js 14 (App Router), Tailwind CSS, Recharts |
| Queue | Upstash Redis (TLS) |
| Operational DB | Neon PostgreSQL (serverless, pooled) |
| Analytics DWH | Snowflake (per-filing MERGE upsert) |
| XBRL parsing | Arelle |
| Orchestration | `pipeline_worker.py` (prod) / Prefect 3 (alt — see above) |
| Observability | Prometheus metrics on `/metrics` |
| CI | GitHub Actions — ruff lint + 34 pytest tests |
| Hosting | Vercel (API + frontend) · Render (worker + poller) |

---

## Local development

```bash
# 1. Start local infrastructure
docker compose up -d postgres redis

# 2. Install dependencies
pip install -e ".[dev]"

# 3. Copy env file
cp .env.example .env   # fill in DATABASE_URL, REDIS_*, SNOWFLAKE_*

# 4. Initialise DB schema
python -c "from shared.utils.db import init_db; init_db()"

# 5. Start API (port 8888 — Docker reserves 8000 on Windows)
uvicorn services.api.main:app --host 127.0.0.1 --port 8888

# 6. Start worker
METRICS_PORT=9100 python services/workers/pipeline_worker.py

# 7. Start poller
POLL_INTERVAL_SECONDS=60 python services/listener/rss_poller.py

# 8. Start frontend
cd frontend && cp .env.local.example .env.local && npm install && npm run dev
```

## Tests

```bash
pytest tests/ -v
```

34 tests: 8-K heuristic parser · S-1 regex extraction · 13F XML parser ·
all FastAPI endpoints · Redis idempotency and form-type filtering.
No network calls — all HTTP is mocked with `respx`.

---

## Deployment

See [DEPLOY.md](DEPLOY.md) for the full production deployment guide.

| Service | Platform | Purpose |
|---------|----------|---------|
| FastAPI backend | Vercel | REST API + status dashboard |
| Next.js frontend | Vercel | Analytics dashboard |
| Pipeline worker | Render | Extracts filings, writes Neon + Snowflake |
| RSS poller | Render | Polls SEC EDGAR every 30 min |
| PostgreSQL | Neon | Operational data store |
| Redis | Upstash | Filing queue + dedup seen-set |
| Data warehouse | Snowflake | Analytics queries |
