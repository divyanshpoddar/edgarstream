# EdgarStream

A production-grade, real-time SEC EDGAR filings pipeline built for sub-minute
latency structured data extraction at scale.

```
RSS Feed (30 s) → Redis queue → Worker (Arelle XBRL) → PostgreSQL + Snowflake
                                    ↓
                            Prometheus / Grafana
                                    ↓
                            FastAPI REST endpoints
```

## Key numbers

| Metric | Value |
|---|---|
| Poll interval | 30 s |
| Median extraction latency (10-K XBRL) | < 60 s |
| Form types ingested | 10-K, 10-Q, 8-K, 13F-HR, S-1 |
| Financial fields extracted | Assets, Liabilities, Revenues, Net Income |
| Snowflake sync | bulk `write_pandas` on every run |
| Test coverage | Golden-file regression suite (Apple 10-K, Berkshire 13F, 8-K) |

---

## Architecture

```
services/
  listener/   rss_poller.py        — polls SEC EDGAR Atom feed every 30 s
  parser/     form_10k.py          — Arelle XBRL, annual period filter (340–380 days)
              form_10q.py          — Arelle XBRL, quarterly period filter (75–97 days)
              form_13f.py          — XML holdings table parser
              form_8k.py           — heuristic event classifier
  workers/    pipeline_worker.py   — Redis consumer loop (bare Python, no deps)
              prefect_flow.py      — Prefect 3 orchestration with retries + UI
  monitor/    schema_drift.py      — detects missing/zero XBRL tags per form type
  api/        main.py              — FastAPI: /api/filings, /api/drift, /api/metrics
  warehouse/  snowflake_sync.py    — bulk sync PostgreSQL → Snowflake

shared/
  models/     filing.py            — Pydantic SECFilingMetadata contract
  utils/      db.py                — SQLAlchemy ORM (PostgreSQL)
  metrics.py                       — Prometheus counters / histograms / gauges

infra/
  prometheus/ prometheus.yml
  grafana/    provisioning/ + dashboards/edgarstream.json
```

---

## Quick start

### Prerequisites

- Docker Desktop
- Python 3.12
- A Snowflake account (optional — pipeline runs without it)

### 1. Start infrastructure

```bash
make up          # starts postgres, redis, prometheus, grafana
```

### 2. Run services locally (dev mode)

Open three terminals:

```bash
make dev         # FastAPI on :8000
make worker      # pipeline worker + Prometheus on :8001
make poller      # RSS poller (polls every 30 s)
```

Or run the Prefect orchestrated worker instead of the bare worker:

```bash
make prefect-dev
```

### 3. Run everything in Docker

```bash
make stack       # docker compose up --build (all services)
make logs        # tail logs for api / worker / poller
```

### 4. Run tests

```bash
pip install -e ".[dev]"
make test
```

Golden-file tests hit real EDGAR URLs and assert financial values within 1% of
known fixtures (Apple FY2023 10-K, Berkshire Q3-2023 13F).

---

## API reference

| Endpoint | Description |
|---|---|
| `GET /api/filings` | Recent processed filings. Params: `form`, `since`, `limit` |
| `GET /api/drift` | Schema drift alerts (missing XBRL tags). Params: `form`, `limit` |
| `GET /api/metrics` | Pipeline health: latency stats, success rate |
| `GET /metrics` | Prometheus scrape endpoint |
| `GET /docs` | Swagger UI |

---

## Observability

Grafana dashboard at **http://localhost:3000** (admin / admin) includes:

- Filings processed / min by form type
- Extraction success rate (target > 95 %)
- Queue depth gauge
- p50 / p95 / p99 extraction latency
- HTTP request rate

Prometheus at **http://localhost:9090**.

---

## Prefect orchestration

The Prefect flow (`services/workers/prefect_flow.py`) wraps every parser call
in a `@task` with automatic retries:

| Task | Retries | Backoff |
|---|---|---|
| 10-K / 10-Q extraction | 3 | 30 s → 60 s → 120 s |
| 13F / 8-K extraction | 2 | 15 s → 30 s |
| DB persistence | 1 | — |

Each filing is a subflow so failures are individually visible in the Prefect UI.

To deploy to a Prefect server:

```bash
prefect deploy --all     # uses prefect.yaml
```

---

## Schema drift detection

`services/monitor/schema_drift.py` runs after every extraction and checks
whether the expected XBRL concepts are present:

- **Missing field** → `SCHEMA_DRIFT` WARNING log + Prometheus counter
  `edgar_schema_drift_total{form_type, missing_field}` + row in `schema_drift_alerts`
- **Zero-valued required field** → same pipeline, labelled `zero:<field>`

Query recent alerts:

```bash
curl http://localhost:8000/api/drift
```

---

## Snowflake sync

```bash
make sync        # reads financial_statements from Postgres, bulk-loads to Snowflake
```

Table: `EDGAR_FINANCIALS` — columns: `ACCESSION_NUMBER`, `COMPANY_NAME`, `CIK`,
`FILING_DATE`, `TOTAL_ASSETS`, `TOTAL_LIABILITIES`, `REVENUES`, `NET_INCOME`,
`SOURCE_XBRL_URL`, `EXTRACTED_AT`.

---

## CI

GitHub Actions (`.github/workflows/ci.yml`) runs on every push / PR to `main`:

1. Spins up Postgres + Redis services
2. `pip install -e ".[dev]"`
3. Runs database migrations
4. Executes the full test suite including golden-file regression tests

---

## Project layout

```
edgarstream/
├── Dockerfile
├── docker-compose.yml
├── prefect.yaml
├── pyproject.toml
├── Makefile
├── .github/workflows/ci.yml
├── infra/
│   ├── prometheus/
│   └── grafana/
├── services/
│   ├── api/
│   ├── listener/
│   ├── monitor/
│   ├── parser/
│   ├── warehouse/
│   └── workers/
├── shared/
│   ├── metrics.py
│   ├── models/
│   └── utils/
└── tests/
    └── test_golden_files.py
```
