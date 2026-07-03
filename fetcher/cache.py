"""Simple on-disk transaction cache.

Caches fetched transactions keyed by (openid, start_date, end_date) so that
re-running an analysis on the same range doesn't re-launch Chromium (which
takes 10+ seconds and hammers the card system).

The cache stores JSON-serializable transaction dicts and is invalidated by
a TTL (default 30 min) — campus card data changes over time, so we don't
want stale results to persist indefinitely.
"""
from __future__ import annotations

import hashlib
import json
import logging
import time
from pathlib import Path
from typing import Optional

from config import _get_config_dir
from fetcher.models import Transaction
from datetime import datetime

logger = logging.getLogger(__name__)

CACHE_DIR = _get_config_dir() / "cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DEFAULT_TTL = 30 * 60  # 30 minutes


def _cache_key(openid: str, start_date: str, end_date: str) -> str:
    """Stable hash key for a fetch request."""
    raw = f"{openid}|{start_date}|{end_date}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def _cache_path(key: str) -> Path:
    return CACHE_DIR / f"{key}.json"


def get_cached(
    openid: str, start_date: str, end_date: str, ttl: int = DEFAULT_TTL
) -> Optional[list[Transaction]]:
    """Return cached transactions if present and fresh, else None."""
    key = _cache_key(openid, start_date, end_date)
    path = _cache_path(key)
    if not path.exists():
        return None

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        logger.warning(f"Corrupt cache file {path}: {e}")
        path.unlink(missing_ok=True)
        return None

    age = time.time() - data.get("ts", 0)
    if age > ttl:
        logger.info(f"Cache stale ({age:.0f}s > {ttl}s), ignoring")
        return None

    try:
        txs = [
            Transaction(
                merchant=item["merchant"],
                amount=item["amount"],
                timestamp=datetime.strptime(item["timestamp"], "%Y-%m-%d %H:%M:%S"),
            )
            for item in data["transactions"]
        ]
        logger.info(f"Cache hit: {len(txs)} transactions ({path.name})")
        return txs
    except (KeyError, ValueError) as e:
        logger.warning(f"Failed to deserialize cache: {e}")
        return None


def set_cached(
    openid: str, start_date: str, end_date: str, transactions: list[Transaction]
) -> None:
    """Persist transactions to cache."""
    key = _cache_key(openid, start_date, end_date)
    path = _cache_path(key)
    data = {
        "ts": time.time(),
        "openid_hash": hashlib.sha256(openid.encode()).hexdigest()[:8],
        "start_date": start_date,
        "end_date": end_date,
        "transactions": [
            {
                "merchant": t.merchant,
                "amount": t.amount,
                "timestamp": t.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
            }
            for t in transactions
        ],
    }
    try:
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        logger.info(f"Cached {len(transactions)} transactions ({path.name})")
    except OSError as e:
        logger.warning(f"Failed to write cache: {e}")


def clear_cache() -> int:
    """Delete all cache files. Returns the number removed."""
    removed = 0
    for p in CACHE_DIR.glob("*.json"):
        try:
            p.unlink()
            removed += 1
        except OSError:
            pass
    logger.info(f"Cleared {removed} cache files")
    return removed


def cache_stats() -> dict:
    """Return summary info about the cache for display in the UI."""
    files = list(CACHE_DIR.glob("*.json"))
    total_size = sum(f.stat().st_size for f in files)
    return {
        "count": len(files),
        "size_mb": round(total_size / (1024 * 1024), 2),
        "dir": str(CACHE_DIR),
    }