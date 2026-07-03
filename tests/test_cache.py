"""Tests for the on-disk transaction cache."""
from datetime import datetime

import pytest

from fetcher import cache
from fetcher.models import Transaction


@pytest.fixture(autouse=True)
def isolated_cache(tmp_path, monkeypatch):
    """Redirect cache dir to a temp folder for each test."""
    monkeypatch.setattr(cache, "CACHE_DIR", tmp_path / "cache")
    cache.CACHE_DIR.mkdir(parents=True, exist_ok=True)
    yield


def _sample_txs():
    return [
        Transaction(merchant="食堂", amount=-12.5, timestamp=datetime(2025, 9, 1, 12, 0, 0)),
        Transaction(merchant="充值", amount=100.0, timestamp=datetime(2025, 9, 2, 9, 0, 0)),
    ]


def test_cache_miss_returns_none():
    assert cache.get_cached("openid", "2025-09-01", "2025-09-30") is None


def test_cache_set_then_get_roundtrip():
    txs = _sample_txs()
    cache.set_cached("openid", "2025-09-01", "2025-09-30", txs)
    loaded = cache.get_cached("openid", "2025-09-01", "2025-09-30")
    assert loaded is not None
    assert len(loaded) == 2
    assert loaded[0].merchant == "食堂"
    assert loaded[0].amount == -12.5
    assert loaded[0].is_expense is True
    assert loaded[1].merchant == "充值"
    assert loaded[1].amount == 100.0
    assert loaded[1].is_expense is False


def test_cache_key_depends_on_all_params():
    txs = _sample_txs()
    cache.set_cached("openid", "2025-09-01", "2025-09-30", txs)
    # Different date range → miss
    assert cache.get_cached("openid", "2025-09-01", "2025-10-31") is None
    # Different openid → miss
    assert cache.get_cached("other", "2025-09-01", "2025-09-30") is None


def test_cache_expires_after_ttl():
    txs = _sample_txs()
    cache.set_cached("openid", "2025-09-01", "2025-09-30", txs)
    # TTL of 0 seconds → immediately stale
    assert cache.get_cached("openid", "2025-09-01", "2025-09-30", ttl=0) is None


def test_clear_cache_removes_files():
    cache.set_cached("openid", "2025-09-01", "2025-09-30", _sample_txs())
    cache.set_cached("openid", "2025-10-01", "2025-10-31", _sample_txs())
    removed = cache.clear_cache()
    assert removed == 2
    assert cache.get_cached("openid", "2025-09-01", "2025-09-30") is None


def test_cache_stats():
    cache.set_cached("openid", "2025-09-01", "2025-09-30", _sample_txs())
    stats = cache.cache_stats()
    assert stats["count"] == 1
    assert stats["size_mb"] >= 0
    assert "dir" in stats


def test_corrupt_cache_returns_none():
    # Write garbage to a cache file matching the key
    txs = _sample_txs()
    cache.set_cached("openid", "2025-09-01", "2025-09-30", txs)
    # Find the file and corrupt it
    files = list(cache.CACHE_DIR.glob("*.json"))
    assert len(files) == 1
    files[0].write_text("{ not valid json", encoding="utf-8")
    assert cache.get_cached("openid", "2025-09-01", "2025-09-30") is None


def test_cache_preserves_transaction_order():
    txs = [
        Transaction(merchant=f"m{i}", amount=-float(i), timestamp=datetime(2025, 9, i + 1, 12, 0, 0))
        for i in range(5)
    ]
    cache.set_cached("openid", "2025-09-01", "2025-09-30", txs)
    loaded = cache.get_cached("openid", "2025-09-01", "2025-09-30")
    assert [t.merchant for t in loaded] == [f"m{i}" for i in range(5)]