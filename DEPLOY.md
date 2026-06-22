# EdgarStream — Deployment Guide

**Architecture**: Two Vercel projects (Next.js frontend + FastAPI backend). Railway runs the
pipeline worker and RSS poller. All four share a single Neon Postgres database and an Upstash
Redis queue (both free tiers).

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  Browser / recruiter                                                         │
│       │                                                                      │
│       ├─────────────────────────────┐                                        │
│       ▼                             ▼                                        │
│  Vercel — Next.js frontend    Vercel — FastAPI backend                       │
│  frontend/  (port 3000 local) api/index.py (port 8888 local)                │
│  ┌──────────────────────┐     ┌─────────────────────────────────┐            │
│  │  /          Home     │────▶│  GET /api/filings               │            │
│  │  /feed      Feed     │     │  GET /api/financials            │            │
│  │  /explore   Explore  │     │  GET /api/metrics               │            │
│  │  /drift     Alerts   │     │  GET /api/volume                │            │
│  └──────────────────────┘     │  GET /api/drift                 │            │
│                                │  GET /status  (HTML dashboard) │            │
│                                └──────────────┬──────────────────┘            │
│                                               │                              │
│                                     ┌─────────▼──────────┐                  │
│                                     │  Neon Postgres      │                  │
│                                     │  (shared DB)        │◀── Railway       │
│                                     └────────────────────┘    worker +      │
│                                     ┌────────────────────┐    poller        │
│                                     │  Upstash Redis      │◀── (always-on)   │
│                                     │  (filing queue)     │                  │
│                                     └────────────────────┘                  │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## Local Development

Run all services locally before deploying. The order matters.

### 1. Start infrastructure (Postgres + Redis via Docker)

```bash
docker compose up -d postgres redis
```

> **Port note**: Docker Desktop on Windows reserves ports 8000 and 8001 via Hyper-V networking.
> The API runs on **8888** and the worker Prometheus metrics run on **9100** locally.

### 2. Initialize the database schema

Run once — creates all tables in Postgres (including `financial_statements` with `form_type`
and `tag_provenance` columns, and `schema_drift_alerts`):

```bash
python -c "from shared.utils.db import init_db; init_db(); print('Done')"
```

If you have an existing database that was created before the `form_type` / `tag_provenance`
columns were added, apply the migration manually:

```bash
python -c "
from shared.utils.db import engine
from sqlalchemy import text
with engine.connect() as conn:
    conn.execute(text('ALTER TABLE financial_statements ADD COLUMN IF NOT EXISTS form_type VARCHAR(10)'))
    conn.execute(text('ALTER TABLE financial_statements ADD COLUMN IF NOT EXISTS tag_provenance TEXT'))
    conn.commit()
    print('Migration applied')
"
```

### 3. Start the FastAPI backend

```bash
uvicorn services.api.main:app --host 127.0.0.1 --port 8888
```

Verify: `curl http://localhost:8888/` → `{"status": "EdgarStream API is live"}`

All API endpoints:

| Endpoint | Description |
|----------|-------------|
| `GET /api/filings` | Recent processed filings (filter: `?form=10-K&limit=20`) |
| `GET /api/financials` | Extracted XBRL financials with tag provenance (filter: `?company=Apple`) |
| `GET /api/metrics` | Pipeline KPIs: latency, success rate, 24h ingestion count |
| `GET /api/volume` | Daily filing counts by form type (param: `?days=7`) |
| `GET /api/drift` | Schema drift alerts (filter: `?form=10-K`) |
| `GET /status` | HTML pipeline dashboard (human-readable) |
| `GET /docs` | FastAPI auto-generated Swagger UI |

### 4. Start the pipeline worker

```bash
METRICS_PORT=9100 python services/workers/pipeline_worker.py
```

The worker pops filings from Redis, extracts XBRL data, persists to Postgres, and exposes
Prometheus metrics on the configured port.

### 5. Start the RSS poller

```bash
python services/listener/rss_poller.py
```

Polls SEC EDGAR every 30 seconds for new 10-K, 10-Q, 8-K, 13F-HR, S-1 filings.
Pushes each new accession to the Redis queue.

### 6. (Optional) Seed the queue with known filings

If the EDGAR feed is quiet (common during off-hours — Form 4s dominate), push known
filings directly to test the pipeline end-to-end:

```bash
python -c "
import httpx, json
from redis import Redis

client = Redis(host='127.0.0.1', port=6379, db=0, decode_responses=True)
QUEUE = 'edgarstream:filing_queue'
HEADERS = {'User-Agent': 'EdgarStreamProject professional-intelligence@firm.com'}

# Apple most-recent 10-Q (correct EDGAR archive URL format)
cik = '320193'
r = httpx.get(f'https://data.sec.gov/submissions/CIK{cik.zfill(10)}.json', headers=HEADERS, timeout=10)
data = r.json()
recent = data['filings']['recent']
for i, form in enumerate(recent['form']):
    if form != '10-Q':
        continue
    acc = recent['accessionNumber'][i]
    filed = recent['filingDate'][i]
    url = f'https://www.sec.gov/Archives/edgar/data/{cik}/{acc.replace(\"-\",\"\")}/{acc}-index.htm'
    client.lpush(QUEUE, json.dumps({
        'accession_number': acc, 'company_name': 'Apple Inc.',
        'cik': cik, 'form_type': '10-Q',
        'filing_date': filed + 'T12:00:00', 'document_url': url,
    }))
    print(f'Queued Apple {form} {filed}')
    break
"
```

### 7. Start the Next.js frontend

```bash
cd frontend
cp .env.local.example .env.local    # NEXT_PUBLIC_API_URL=http://localhost:8888
npm install
npm run dev                          # http://localhost:3000
```

Open **http://localhost:3000** in your browser.

---

## Production Deployment

### Step 1 — Neon Postgres (shared database)

**Already provisioned.** The Neon project is live and all tables have been initialized.

The `DATABASE_URL` in `.env` is already set to the Neon pooler endpoint. Copy that value
into Vercel and Railway as shown below.

The connection string format (replace the placeholder with your actual Neon URL):
```
postgresql+psycopg2://neondb_owner:<password>@ep-<slug>-pooler.<region>.aws.neon.tech/neondb?sslmode=require&channel_binding=require
```

> The `+psycopg2` dialect prefix and `channel_binding=require` parameter are both required.
> Neon's pooler endpoint (`-pooler` in the hostname) is used — it handles connection pooling
> automatically, which is important for serverless (Vercel) invocations.

### Step 2 — Upstash Redis (shared queue)

**Already provisioned.** The Upstash database is live and the connection has been verified.
Connection details are in `.env` under `REDIS_HOST`, `REDIS_PORT`, `REDIS_PASSWORD`, `REDIS_SSL`.

The values to paste into Railway (from `.env`):
```
REDIS_HOST=tidy-redbird-95981.upstash.io
REDIS_PORT=6379
REDIS_PASSWORD=<from .env>
REDIS_SSL=true
```

Both the worker and poller connect via `redis-py` with TLS enabled:

```python
redis_client = Redis(
    host=os.getenv("REDIS_HOST", "localhost"),
    port=int(os.getenv("REDIS_PORT", 6379)),
    password=os.getenv("REDIS_PASSWORD", None),
    ssl=os.getenv("REDIS_SSL", "false").lower() == "true",
    db=0,
    decode_responses=True,
)
```

> **Note**: The `UPSTASH_REDIS_REST_URL` and token shown in the Upstash dashboard are for
> their HTTP REST API — we don't use those. Our pipeline uses the standard Redis protocol
> via the `rediss://` (TLS) endpoint, which `redis-py` handles natively.

### Step 3 — Deploy FastAPI backend to Vercel (Project 1)

#### 3a. Push repo to GitHub

```bash
git init
git add .
git commit -m "EdgarStream: real-time SEC EDGAR pipeline"
gh repo create edgarstream --public --source . --push
```

> **Security**: move Snowflake credentials out of source before pushing.
> See the [Snowflake credentials](#snowflake-credentials) section below.

#### 3b. Create Vercel project for the API

1. **vercel.com** → "Add New Project" → import your GitHub repo
2. Framework preset: **Other**
3. Root directory: `/` (leave as default — `vercel.json` is at the root)
4. Vercel auto-detects `vercel.json` and uses `api/index.py` as the entry point

#### 3c. Set environment variables (API project)

| Variable | Value |
|----------|-------|
| `DATABASE_URL` | `postgresql+psycopg2://...?sslmode=require` |

Click **Deploy**.

#### 3d. Initialize the database schema on Neon

Run once from your local machine after the first deploy:

```bash
DATABASE_URL="postgresql+psycopg2://...?sslmode=require" \
  python -c "from shared.utils.db import init_db; init_db(); print('Tables created')"
```

Your API endpoints will be live at:
```
https://edgarstream-api.vercel.app/
https://edgarstream-api.vercel.app/status
https://edgarstream-api.vercel.app/api/filings
https://edgarstream-api.vercel.app/api/financials
https://edgarstream-api.vercel.app/api/metrics
https://edgarstream-api.vercel.app/api/volume
https://edgarstream-api.vercel.app/api/drift
```

### Step 4 — Deploy Next.js frontend to Vercel (Project 2)

#### 4a. Create a second Vercel project

1. **vercel.com** → "Add New Project" → same GitHub repo
2. **Change Root Directory to `frontend`** before clicking Deploy
3. Framework preset: **Next.js** (auto-detected)

#### 4b. Set environment variables (frontend project)

| Variable | Value |
|----------|-------|
| `NEXT_PUBLIC_API_URL` | Your API project URL, e.g. `https://edgarstream-api.vercel.app` |

Click **Deploy**. Pages live at:

```
https://edgarstream-app.vercel.app/           # Home: KPIs + volume chart
https://edgarstream-app.vercel.app/feed       # Live filing feed with filters
https://edgarstream-app.vercel.app/explore    # Company XBRL financial explorer
https://edgarstream-app.vercel.app/drift      # Schema drift alerts
```

### Step 5 — Deploy worker + poller to Railway

#### 5a. Install Railway CLI

```bash
npm install -g @railway/cli
railway login
```

#### 5b. Create the project

```bash
railway init    # choose "Empty project", name it edgarstream-workers
```

#### 5c. Service 1 — pipeline worker

```bash
railway service create --name edgarstream-worker
railway link
railway up      # deploys via railway.toml (start command: pipeline_worker.py)
```

Set environment variables:

```bash
railway variables set DATABASE_URL="postgresql+psycopg2://...?sslmode=require"
railway variables set REDIS_HOST="global-xxx.upstash.io"
railway variables set REDIS_PORT="6379"
railway variables set REDIS_PASSWORD="xxx"
railway variables set REDIS_SSL="true"
railway variables set METRICS_PORT="9100"
```

#### 5d. Service 2 — RSS poller

In the Railway dashboard → your project → **New Service** → GitHub Repo:
- Same repo
- Override start command: `python services/listener/rss_poller.py`
- Add the same env vars as above (except `METRICS_PORT` — poller doesn't expose metrics)

#### 5e. Verify both services are running

```bash
railway logs --service edgarstream-worker
# Expected: "Worker pool listening for real-time pipeline payloads..."

railway logs --service edgarstream-poller
# Expected: "Poll complete. Queued N clean filings."
```

---

## Step 6 — Smoke test

Replace `API` and `APP` with your actual Vercel URLs:

```bash
API=https://edgarstream-api.vercel.app
APP=https://edgarstream-app.vercel.app

# Backend
curl $API/                              # {"status": "EdgarStream API is live"}
curl $API/status                        # HTML dashboard (open in browser)
curl "$API/api/filings?limit=5"         # JSON filing list
curl "$API/api/financials?company=Apple" # XBRL data with tag provenance
curl "$API/api/metrics"                 # KPI metrics
curl "$API/api/volume?days=7"           # Daily counts by form type
curl "$API/api/drift?limit=5"           # Schema drift alerts

# Frontend (open in browser)
open $APP/                              # Home: KPIs + bar chart
open $APP/feed                          # Live filings with filter bar
open $APP/explore                       # Search "Apple" → see $371B assets + XBRL tags
open $APP/drift                         # Drift alert table
```

---

## Custom domain (optional, ~$12/yr)

1. Buy `edgarstream.io` on Namecheap
2. Vercel (frontend project) → Settings → Domains → add `edgarstream.io`
3. Add a CNAME DNS record: `@` → `cname.vercel-dns.com`
4. Vercel (API project) → Settings → Domains → add `api.edgarstream.io`
5. SSL is auto-provisioned (Let's Encrypt)
6. Update the frontend env var: `NEXT_PUBLIC_API_URL=https://api.edgarstream.io`

Public URLs:
```
https://edgarstream.io/            # Next.js home
https://edgarstream.io/explore     # Financial explorer (the recruiter showcase)
https://api.edgarstream.io/status  # Pipeline status dashboard
```

---

## Snowflake credentials

`services/warehouse/snowflake_sync.py` has hardcoded credentials. Fix before pushing to GitHub:

1. Replace hardcoded values:
   ```python
   import os
   conn = snowflake.connector.connect(
       user=os.getenv("SNOWFLAKE_USER"),
       password=os.getenv("SNOWFLAKE_PASSWORD"),
       account=os.getenv("SNOWFLAKE_ACCOUNT"),
   )
   ```

2. Add to Railway worker service:
   ```bash
   railway variables set SNOWFLAKE_USER=DIVYANSHPODDAR
   railway variables set SNOWFLAKE_PASSWORD=<your password>
   railway variables set SNOWFLAKE_ACCOUNT=USB09882
   ```

3. Do **not** add Snowflake vars to Vercel — the API never touches Snowflake.

---

## Environment variable reference

### FastAPI backend (Vercel + Railway worker + Railway poller)

| Variable | Default (local) | Required in prod |
|----------|-----------------|------------------|
| `DATABASE_URL` | `postgresql+psycopg2://edgar_user:edgar_password@127.0.0.1:5434/edgar_metadata` | Yes — Neon URL |
| `REDIS_HOST` | `localhost` | Yes — Upstash hostname |
| `REDIS_PORT` | `6379` | Yes |
| `REDIS_PASSWORD` | _(none)_ | Yes — Upstash password |
| `REDIS_SSL` | `false` | `true` for Upstash |
| `METRICS_PORT` | `9100` | Optional (worker only) |

### Next.js frontend (Vercel)

| Variable | Local value | Prod value |
|----------|-------------|------------|
| `NEXT_PUBLIC_API_URL` | `http://localhost:8888` | `https://edgarstream-api.vercel.app` |

### Railway only (worker)

| Variable | Value |
|----------|-------|
| `SNOWFLAKE_USER` | Your Snowflake username |
| `SNOWFLAKE_PASSWORD` | Your Snowflake password |
| `SNOWFLAKE_ACCOUNT` | Your Snowflake account identifier |

---

## Free tier limits

| Service | Free limit | Estimated EdgarStream usage |
|---------|------------|-----------------------------|
| Vercel (API) | 100 GB-hrs/mo, 100k invocations | ~1k API calls/day → well within limit |
| Vercel (Frontend) | 100 GB bandwidth/mo | Static + SSR pages → minimal |
| Railway | $5 credit/mo (~500 container-hrs) | Worker + poller: ~$2–3/mo combined |
| Neon | 512 MB storage, 190 compute-hrs/mo | Filing logs + financials: ~50 MB/mo |
| Upstash Redis | 10k commands/day | Queue pushes + pops: ~500/day → fine |
