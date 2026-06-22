"""
Tests for pipeline idempotency guarantees:
- Same accession number is never queued twice (Redis seen-set)
- Unsupported form types are filtered out
- Supported form types are accepted
"""
from unittest.mock import MagicMock, call


def _make_redis_mock():
    """Return a mock Redis client with a simulated seen-set."""
    seen = set()
    mock = MagicMock()
    mock.sismember.side_effect = lambda key, val: val in seen
    mock.sadd.side_effect = lambda key, val: seen.add(val)
    mock.lpush = MagicMock()
    return mock, seen


def test_same_accession_queued_only_once(monkeypatch):
    from services.listener import rss_poller

    redis_mock, seen = _make_redis_mock()
    monkeypatch.setattr(rss_poller, "redis_client", redis_mock)

    # Simulate two feed entries with the same accession
    entry = {
        "link": "https://www.sec.gov/Archives/edgar/data/320193/000032019326000001/0000320193-26-000001-index.htm",
        "title": "10-K - Apple Inc. (0000320193)",
        "updated": "2026-06-01T12:00:00",
    }

    import feedparser
    fake_feed = MagicMock()
    fake_feed.entries = [entry, entry]  # same entry twice

    import httpx
    monkeypatch.setattr(rss_poller.httpx, "get", MagicMock(
        return_value=MagicMock(text="<feed/>", raise_for_status=MagicMock())
    ))
    monkeypatch.setattr(rss_poller.feedparser, "parse", lambda _: fake_feed)

    rss_poller.parse_sec_feed()

    # lpush should have been called exactly once despite two identical entries
    assert redis_mock.lpush.call_count == 1


def test_unsupported_form_type_not_queued(monkeypatch):
    from services.listener import rss_poller

    redis_mock, _ = _make_redis_mock()
    monkeypatch.setattr(rss_poller, "redis_client", redis_mock)

    entry = {
        "link": "https://www.sec.gov/Archives/edgar/data/320193/000032019326000001/0000320193-26-000002-index.htm",
        "title": "4 - Apple Inc. (0000320193)",  # Form 4 — not supported
        "updated": "2026-06-01T12:00:00",
    }

    fake_feed = MagicMock()
    fake_feed.entries = [entry]

    monkeypatch.setattr(rss_poller.httpx, "get", MagicMock(
        return_value=MagicMock(text="<feed/>", raise_for_status=MagicMock())
    ))
    monkeypatch.setattr(rss_poller.feedparser, "parse", lambda _: fake_feed)

    rss_poller.parse_sec_feed()

    assert redis_mock.lpush.call_count == 0


def test_all_supported_form_types_are_queued(monkeypatch):
    from services.listener import rss_poller

    redis_mock, _ = _make_redis_mock()
    monkeypatch.setattr(rss_poller, "redis_client", redis_mock)

    supported = ["10-K", "10-Q", "8-K", "13F-HR", "13F-HR/A", "S-1", "S-1/A"]
    entries = [
        {
            "link": f"https://www.sec.gov/Archives/edgar/data/1/00000000000000000{i}-26-000001-index.htm",
            "title": f"{form} - Test Corp (000000000{i})",
            "updated": "2026-06-01T12:00:00",
        }
        for i, form in enumerate(supported)
    ]

    fake_feed = MagicMock()
    fake_feed.entries = entries

    monkeypatch.setattr(rss_poller.httpx, "get", MagicMock(
        return_value=MagicMock(text="<feed/>", raise_for_status=MagicMock())
    ))
    monkeypatch.setattr(rss_poller.feedparser, "parse", lambda _: fake_feed)

    rss_poller.parse_sec_feed()

    assert redis_mock.lpush.call_count == len(supported)


def test_feed_http_error_does_not_crash(monkeypatch):
    from services.listener import rss_poller
    import httpx

    redis_mock, _ = _make_redis_mock()
    monkeypatch.setattr(rss_poller, "redis_client", redis_mock)

    def _raise(*args, **kwargs):
        raise httpx.ConnectError("Connection refused")

    monkeypatch.setattr(rss_poller.httpx, "get", _raise)

    # Should not raise — errors are caught and logged
    rss_poller.parse_sec_feed()
    assert redis_mock.lpush.call_count == 0
