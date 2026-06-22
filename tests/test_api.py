"""
Smoke tests for FastAPI endpoints — all DB calls are mocked.
"""


def test_root(api_client):
    r = api_client.get("/")
    assert r.status_code == 200
    assert r.json()["status"] == "EdgarStream API is live"


def test_status_page_is_html(api_client):
    r = api_client.get("/status")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    assert b"EdgarStream" in r.content


def test_filings_returns_list(api_client):
    r = api_client.get("/api/filings")
    assert r.status_code == 200
    body = r.json()
    assert "filings" in body or "count" in body


def test_filings_limit_param(api_client):
    r = api_client.get("/api/filings?limit=5")
    assert r.status_code == 200


def test_financials_returns_list(api_client):
    r = api_client.get("/api/financials")
    assert r.status_code == 200
    body = r.json()
    assert "financials" in body or "count" in body


def test_financials_company_filter(api_client):
    r = api_client.get("/api/financials?company=Apple")
    assert r.status_code == 200


def test_metrics_returns_expected_keys(api_client):
    r = api_client.get("/api/metrics")
    assert r.status_code == 200
    body = r.json()
    assert "total_filings_ingested" in body
    assert "pipeline_health" in body
    assert "extraction_success_rate" in body["pipeline_health"]


def test_drift_returns_list(api_client):
    r = api_client.get("/api/drift")
    assert r.status_code == 200
    body = r.json()
    assert "alerts" in body or "count" in body


def test_volume_returns_list(api_client):
    r = api_client.get("/api/volume?days=7")
    assert r.status_code == 200


def test_docs_endpoint(api_client):
    r = api_client.get("/docs")
    assert r.status_code == 200
