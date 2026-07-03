"""Tests for the recursive 'find first record' endpoint."""
from datetime import date, datetime

import pytest

from app import (
    app,
    _state,
    _state_lock,
    get_cached_first_date,
    cache_first_date,
)
from fetcher.models import Transaction


@pytest.fixture
def client():
    return app.test_client()


@pytest.fixture
def reset_state():
    with _state_lock:
        _state["transactions"] = None
        _state["analysis"] = None
        _state["status"] = "idle"
    yield
    with _state_lock:
        _state["transactions"] = None
        _state["analysis"] = None
        _state["status"] = "idle"


def _wait_for_state_change(timeout: float = 5.0) -> None:
    import time
    for _ in range(int(timeout * 10)):
        with _state_lock:
            if _state["status"] in ("done", "error"):
                return
        time.sleep(0.1)


def test_find_first_rejects_empty_url(client):
    r = client.post("/api/fetch/first", json={})
    assert r.status_code == 400
    assert "error" in r.get_json()


def test_find_first_rejects_invalid_url(client):
    r = client.post("/api/fetch/first", json={"url": "https://example.com/?openid=abc"})
    assert r.status_code == 400


def test_find_first_rejects_url_without_openid(client):
    r = client.post("/api/fetch/first", json={"url": "https://mcard.buct.edu.cn/page"})
    assert r.status_code == 400


def test_find_first_starts_in_background(client, reset_state, monkeypatch):
    """The endpoint must return immediately with status=started, then
    populate _state asynchronously."""
    import app as app_mod
    calls = []

    def fake_find(openid, max_lookback_years=10, on_progress=None):
        calls.append(openid)
        return (
            [Transaction("x", -1.0, datetime(2022, 9, 1, 12, 0))],
            date(2022, 9, 1),
        )

    monkeypatch.setattr(app_mod, "find_and_fetch_all", fake_find)

    r = client.post("/api/fetch/first", json={
        "url": "https://mcard.buct.edu.cn/page?openid=ABC123"
    })
    assert r.status_code == 200
    assert r.get_json()["status"] == "started"

    _wait_for_state_change()

    with _state_lock:
        assert _state["status"] == "done"
        assert _state["transactions"] is not None
        assert len(_state["transactions"]) == 1
        assert _state["analysis"] is not None
        msg = _state["message"]
    assert "2022-09-01" in msg
    assert "1" in msg
    assert calls == ["ABC123"]


def test_find_first_caches_first_date(client, reset_state, monkeypatch):
    """After a successful find, the openid->date cache is populated, and
    a second call uses the cache (no second find_and_fetch_all call)."""
    import app as app_mod
    call_count = {"n": 0}

    def fake_find(openid, max_lookback_years=10, on_progress=None):
        call_count["n"] += 1
        return (
            [Transaction("x", -1.0, datetime(2021, 9, 1, 12, 0))],
            date(2021, 9, 1),
        )

    monkeypatch.setattr(app_mod, "find_and_fetch_all", fake_find)

    url = "https://mcard.buct.edu.cn/page?openid=CACHE_TEST"
    r1 = client.post("/api/fetch/first", json={"url": url})
    assert r1.status_code == 200
    _wait_for_state_change()
    assert call_count["n"] == 1
    assert get_cached_first_date("CACHE_TEST") == "2021-09-01"

    # Reset state but keep the cache
    with _state_lock:
        _state["status"] = "idle"
        _state["transactions"] = None

    # Second call: cache hit, find_and_fetch_all NOT called again
    r2 = client.post("/api/fetch/first", json={"url": url})
    assert r2.status_code == 200
    _wait_for_state_change()
    assert call_count["n"] == 1, "second call should use cache, not re-walk"


def test_find_first_force_recurse_bypasses_cache(client, reset_state, monkeypatch):
    """force_recurse=true must invalidate the cache for this call."""
    import app as app_mod
    call_count = {"n": 0}

    def fake_find(openid, max_lookback_years=10, on_progress=None):
        call_count["n"] += 1
        return (
            [Transaction("x", -1.0, datetime(2021, 9, 1, 12, 0))],
            date(2021, 9, 1),
        )

    monkeypatch.setattr(app_mod, "find_and_fetch_all", fake_find)
    cache_first_date("FORCE_TEST", "2021-09-01")

    url = "https://mcard.buct.edu.cn/page?openid=FORCE_TEST"
    r = client.post("/api/fetch/first", json={"url": url, "force_recurse": True})
    assert r.status_code == 200
    _wait_for_state_change()
    assert call_count["n"] == 1


def test_find_first_handles_empty_result(client, reset_state, monkeypatch):
    """If find_and_fetch_all returns no records, the endpoint must surface
    that as a 'done' status with a clear message, not crash."""
    import app as app_mod

    def fake_find(openid, max_lookback_years=10, on_progress=None):
        return [], None

    monkeypatch.setattr(app_mod, "find_and_fetch_all", fake_find)

    r = client.post("/api/fetch/first", json={
        "url": "https://mcard.buct.edu.cn/page?openid=EMPTY"
    })
    assert r.status_code == 200
    _wait_for_state_change()
    with _state_lock:
        assert _state["status"] == "done"
        assert "未找到" in _state["message"]
        assert _state["transactions"] is None


def test_find_first_rejects_when_already_fetching(client, reset_state):
    """Concurrent /api/fetch/first calls must not both spawn workers."""
    with _state_lock:
        _state["status"] = "fetching"
    try:
        r = client.post("/api/fetch/first", json={
            "url": "https://mcard.buct.edu.cn/page?openid=BUSY"
        })
        assert r.status_code == 409
    finally:
        with _state_lock:
            _state["status"] = "idle"
