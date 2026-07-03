# fetcher/browser.py
import time
import logging
from datetime import datetime, timedelta
from typing import Callable, Optional
from playwright.sync_api import sync_playwright
from fetcher.models import Transaction
from config import get_config

logger = logging.getLogger(__name__)

SELFTRADE_URL = "{base}/selftrade/openQueryCardSelfTrade?openid={openid}&displayflag=1&id=23"
MAX_DAYS = 31

# JS to monkey-patch $.ajax and capture API responses.
#
# jQuery's $.ajax has two call signatures — $.ajax(url, settings) and
# $.ajax(settings) — and some page wrappers invoke it with null/undefined.
# We normalize every call down to a single settings object so reading
# .success / .error can never throw (the previous version crashed with
# "Cannot read properties of null" when opts was null). The patch is also
# idempotent so a re-evaluate won't double-wrap and cause infinite recursion.
PATCH_JS = """
() => {
    if (window.__cardAjaxPatched) return;
    var jq = (typeof jQuery !== 'undefined') ? jQuery
            : (typeof $ !== 'undefined') ? $ : null;
    if (!jq || !jq.ajax) return;
    window.__cardAjaxPatched = true;
    window.__cardData = window.__cardData || [];
    window.__cardFetchError = null;

    var origAjax = jq.ajax;

    jq.ajax = function (url, options) {
        // Normalize jQuery call signatures into one settings object.
        var settings;
        if (typeof url === 'string') {
            settings = options || {};
            settings.url = url;
        } else {
            settings = url || {};
        }

        var origSuccess = settings.success;
        var origError = settings.error;

        settings.success = function (data) {
            try {
                if (settings.url && settings.url.indexOf('queryCardSelfTradeList') !== -1) {
                    if (data && data.success && data.resultData) {
                        var items = data.resultData;
                        for (var i = 0; i < items.length; i++) {
                            window.__cardData.push(items[i]);
                        }
                    }
                }
            } catch (e) {
                window.__cardFetchError = 'capture: ' + e;
            }
            if (typeof origSuccess === 'function') {
                origSuccess.apply(this, arguments);
            }
        };

        settings.error = function (xhr, status, err) {
            window.__cardFetchError = status + ': ' + err;
            if (typeof origError === 'function') {
                origError.apply(this, arguments);
            }
        };

        return origAjax.call(this, settings);
    };
}
"""

# JS to trigger a query for a specific date range
TRIGGER_QUERY_JS = """
(args) => {
    document.getElementById('beginTime').value = args[0];
    document.getElementById('endTime').value = args[1];
    queryTrade();
}
"""

def fetch_transactions(
    openid: str,
    start_date: str = "2025-09-01",
    end_date: str | None = None,
    on_progress: Optional[Callable[[str, int], None]] = None,
    stop_after_empty: int = 0,
) -> list[Transaction]:
    """Fetch all transactions from BUCT card system via Playwright.

    Args:
        openid: User's WeChat openid for the card system.
        start_date: Earliest date to fetch (YYYY-MM-DD).
        end_date: Latest date (defaults to today). Format: YYYY-MM-DD.
        on_progress: Callback(message: str, count: int) for progress updates.
        stop_after_empty: If > 0, halt the backward walk after this many
            consecutive batches that returned no new records. Used by the
            "find first record" flow to stop shortly after we've gone past
            the earliest transaction, instead of always walking all the way
            back to start_date.

    Returns:
        List of Transaction objects, newest first.
    """
    if end_date is None:
        end_date = datetime.now().strftime("%Y-%m-%d")

    cfg = get_config()
    url = SELFTRADE_URL.format(base=cfg.card_base_url, openid=openid)

    all_data: list[dict] = []
    start = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        logger.info(f"Navigating to card system: {url}")
        page.goto(url, wait_until="networkidle", timeout=30000)

        # Wait for jQuery to be available before patching. networkidle usually
        # guarantees this, but asserting explicitly turns a slow/broken page
        # into a clear error instead of a downstream null-deref.
        try:
            page.wait_for_function(
                "() => (typeof jQuery !== 'undefined') || (typeof $ !== 'undefined')",
                timeout=10000,
            )
        except Exception:
            logger.warning("jQuery did not become available; ajax patch may not apply")

        # Inject the monkey-patch (idempotent + null-safe)
        page.evaluate(PATCH_JS)

        # Walk backwards from end_date in MAX_DAYS chunks
        cursor = end
        batch_num = 0
        consecutive_empty = 0
        while cursor > start:
            batch_num += 1
            batch_begin = cursor - timedelta(days=MAX_DAYS - 1)
            if batch_begin < start:
                batch_begin = start

            begin_str = batch_begin.strftime("%Y-%m-%d")
            end_str = cursor.strftime("%Y-%m-%d")

            logger.info(f"Batch {batch_num}: {begin_str} ~ {end_str}")
            if on_progress:
                on_progress(f"正在查询 {begin_str} ~ {end_str}", len(all_data))

            count_before = len(all_data)

            # Trigger query
            page.evaluate(TRIGGER_QUERY_JS, [begin_str, end_str])
            time.sleep(2)

            # Read captured data
            new_data = page.evaluate("window.__cardData")
            if len(new_data) > count_before:
                all_data = new_data[:]
                consecutive_empty = 0
            else:
                consecutive_empty += 1
                if stop_after_empty and consecutive_empty >= stop_after_empty:
                    logger.info(
                        f"Early stop after {consecutive_empty} consecutive empty batches"
                    )
                    break

            logger.info(f"  -> captured {len(all_data) - count_before} new records (total: {len(all_data)})")

            # Move cursor back
            cursor = batch_begin - timedelta(days=1)

        # Check for errors
        error = page.evaluate("window.__cardFetchError")
        if error:
            logger.warning(f"Fetch error encountered: {error}")

        browser.close()

    # Convert to Transaction objects
    transactions = []
    for item in all_data:
        try:
            tx = Transaction(
                merchant=item.get("mername", "未知"),
                amount=float(item.get("txamt", 0)),
                timestamp=datetime.strptime(item["txdate"], "%Y-%m-%d %H:%M:%S"),
            )
            transactions.append(tx)
        except (KeyError, ValueError) as e:
            logger.warning(f"Skipping malformed record: {item} ({e})")

    # Sort newest first
    transactions.sort(key=lambda t: t.timestamp, reverse=True)

    if on_progress:
        on_progress(f"完成，共 {len(transactions)} 条记录", len(transactions))

    logger.info(f"Fetched {len(transactions)} transactions")
    return transactions


def find_and_fetch_all(
    openid: str,
    max_lookback_years: int = 10,
    on_progress: Optional[Callable[[str, int], None]] = None,
) -> tuple[list[Transaction], Optional["datetime.date"]]:
    """Recursively walk the card system backward to find the first record.

    Strategy: ask the card system for a wide range (today minus
    max_lookback_years) and let ``fetch_transactions`` walk backward in
    31-day batches, halting after 3 consecutive empty batches. Once the
    walk stops, the oldest transaction in the returned list is the first
    record we have.

    The 3-batch tolerance absorbs random empty chunks (a single batch with
    no data shouldn't trigger an early stop — the card system can
    occasionally return nothing for short windows where records exist).

    Args:
        openid: Campus card openid.
        max_lookback_years: Upper bound for the search. The card system
            only goes back ~10 years for typical students; tune higher if
            needed.
        on_progress: Same signature as for ``fetch_transactions``.

    Returns:
        (transactions, first_date) — empty list and None if no records
        were found at all.
    """
    from datetime import date as _date, timedelta as _td

    today = _date.today()
    earliest = today.replace(year=today.year - max_lookback_years)

    if on_progress:
        on_progress(
            f"正在递归查找最早记录（最早探测 {earliest}）...", 0
        )

    txs = fetch_transactions(
        openid,
        earliest.strftime("%Y-%m-%d"),
        today.strftime("%Y-%m-%d"),
        on_progress=on_progress,
        stop_after_empty=3,
    )

    if not txs:
        return [], None

    first_date = min(t.timestamp.date() for t in txs)
    if on_progress:
        on_progress(
            f"找到最早记录: {first_date}（共 {len(txs)} 笔）", len(txs)
        )
    return txs, first_date
