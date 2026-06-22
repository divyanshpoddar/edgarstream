.PHONY: build up down dev worker poller prefect-dev prefect-deploy test migrate sync reset stack logs

# ── Docker ───────────────────────────────────────────────────────────────────

build:
	docker compose build

up:
	docker compose up -d postgres redis prometheus grafana

down:
	docker compose down

# Start the full stack (infra + app services) in Docker
stack:
	docker compose up -d --build

# Show logs for all app services
logs:
	docker compose logs -f api worker poller

# ── Local dev (runs services on host, connects to Dockerised infra) ──────────

dev:
	uvicorn services.api.main:app --host 0.0.0.0 --port 8000 --reload

worker:
	python services/workers/pipeline_worker.py

# Run Prefect orchestrated worker (retries + UI visibility) locally
prefect-dev:
	python services/workers/prefect_flow.py

# Deploy to Prefect Cloud / self-hosted Prefect server
prefect-deploy:
	prefect deploy --all

poller:
	python services/listener/rss_poller.py

# ── Database / Redis ─────────────────────────────────────────────────────────

migrate:
	python -c "from shared.utils.db import init_db; init_db(); print('DB migrated')"

reset:
	python -c "from shared.utils.db import engine, Base; Base.metadata.drop_all(bind=engine); Base.metadata.create_all(bind=engine); print('DB reset')"
	python -c "from redis import Redis; r = Redis(host='localhost', port=6379, db=0); r.delete('edgarstream:filing_queue'); r.delete('edgarstream:seen_accession_numbers'); print('Redis reset')"

# ── Tests / Warehouse ─────────────────────────────────────────────────────────

test:
	pytest tests/ -v --tb=short

sync:
	python services/warehouse/snowflake_sync.py
