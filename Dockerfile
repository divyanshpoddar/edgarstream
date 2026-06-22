FROM python:3.12-slim

# gcc + libpq-dev are needed by psycopg2-binary and lxml C extensions
RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc \
        libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# ── Dependency layer ─────────────────────────────────────────────────────────
# Copy pyproject.toml first and install all Python deps before touching source.
# This layer is cached until pyproject.toml changes, so slow packages (Arelle,
# pandas, snowflake-connector) are not reinstalled on every code change.
#
# We stub out package __init__.py files so setuptools can scan the layout;
# editable install (-e) creates a .pth pointing at /app, so the real source
# copied in the next stage is picked up automatically.
COPY pyproject.toml README.md ./
RUN python -c "\
import os; \
dirs = ['shared','shared/utils','shared/models', \
        'services','services/api','services/listener', \
        'services/parser','services/warehouse','services/workers']; \
[os.makedirs(d, exist_ok=True) or open(f'{d}/__init__.py','w').close() for d in dirs]" \
 && pip install --no-cache-dir -e .

# ── Source layer ─────────────────────────────────────────────────────────────
COPY shared/ shared/
COPY services/ services/

# Run as non-root
RUN useradd -m -u 1000 edgar && chown -R edgar:edgar /app
USER edgar

# 8000 = FastAPI, 8001 = worker Prometheus endpoint
EXPOSE 8000 8001
