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
) -> list[Transaction]:
    """Fetch all transactions from BUCT card system via Playwright.

    Args:
        openid: User's WeChat openid for the card system.
        start_date: Earliest date to fetch (YYYY-MM-DD).
        end_date: Latest date (defaults to today). Format: YYYY-MM-DD.
        on_progress: Callback(message: str, count: int) for progress updates.

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
