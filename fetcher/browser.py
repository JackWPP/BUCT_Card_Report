# fetcher/browser.py
import time
import logging
from datetime import datetime, timedelta
from typing import Callable, Optional
from playwright.sync_api import sync_playwright
from fetcher.models import Transaction
from config import Config

logger = logging.getLogger(__name__)

SELFTRADE_URL = "{base}/selftrade/openQueryCardSelfTrade?openid={openid}&displayflag=1&id=23"
MAX_DAYS = 31

# JS to monkey-patch $.ajax and capture API responses
PATCH_JS = """
window.__cardData = [];
window.__cardFetchDone = false;
window.__cardFetchError = null;
const origAjax = $.ajax;
$.ajax = function(opts) {
    const origSuccess = opts.success;
    opts.success = function(data) {
        if (opts.url && opts.url.indexOf('queryCardSelfTradeList') !== -1) {
            if (data && data.success && data.resultData) {
                for (const item of data.resultData) {
                    window.__cardData.push(item);
                }
            }
        }
        if (origSuccess) origSuccess.apply(this, arguments);
    };
    const origError = opts.error;
    opts.error = function(xhr, status, err) {
        window.__cardFetchError = status + ': ' + err;
        if (origError) origError.apply(this, arguments);
    };
    return origAjax.apply(this, arguments);
};
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

    cfg = Config()
    url = SELFTRADE_URL.format(base=cfg.card_base_url, openid=openid)

    all_data: list[dict] = []
    start = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        logger.info(f"Navigating to card system: {url}")
        page.goto(url, wait_until="networkidle", timeout=30000)
        time.sleep(1)

        # Inject the monkey-patch
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
