import os

# Set before any app imports so db.py picks up the right dialect
os.environ.setdefault("DATABASE_URL", "sqlite:///./test.db")
os.environ.setdefault("REDIS_HOST", "localhost")
os.environ.setdefault("REDIS_PORT", "6379")
os.environ.setdefault("REDIS_SSL", "false")
os.environ.setdefault("SNOWFLAKE_USER", "")
os.environ.setdefault("SNOWFLAKE_PASSWORD", "")
os.environ.setdefault("SNOWFLAKE_ACCOUNT", "")

import pytest
from pathlib import Path
from unittest.mock import MagicMock
from fastapi.testclient import TestClient

FIXTURES = Path(__file__).parent / "fixtures"


def _fixture(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


@pytest.fixture(scope="session")
def api_client():
    from services.api.main import app, get_db

    def _mock_db():
        db = MagicMock()
        db.query.return_value.filter.return_value.order_by.return_value \
            .limit.return_value.all.return_value = []
        db.query.return_value.order_by.return_value \
            .limit.return_value.all.return_value = []
        db.query.return_value.filter.return_value.count.return_value = 0
        db.query.return_value.count.return_value = 0
        db.query.return_value.filter.return_value \
            .group_by.return_value.all.return_value = []
        db.execute.return_value.fetchall.return_value = []
        yield db

    app.dependency_overrides[get_db] = _mock_db
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def fixture_bytes():
    return _fixture
