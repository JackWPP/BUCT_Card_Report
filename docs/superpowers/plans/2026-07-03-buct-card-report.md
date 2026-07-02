# BUCT_Card_Report Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a lightweight Flask web app that fetches campus card transaction data from BUCT's card system via Playwright browser automation, analyzes spending patterns, and generates beautiful HTML reports — with optional LLM-powered personalized insights.

**Architecture:** Flask serves a single-page Web UI. User pastes a campus card URL (containing their WeChat OAuth `openid`). Backend launches Playwright to batch-fetch transaction data via the card system's AJAX API. Built-in analyzers compute statistics (monthly trends, category breakdown, merchant rankings, meal time distribution). Report renderer produces a self-contained HTML dashboard with Chart.js visualizations. Optional LLM integration (OpenAI-compatible API) adds personalized textual insights.

**Tech Stack:** Python 3.10+, Flask, Playwright, pandas, Jinja2, Chart.js (CDN), openai (Python SDK)

## Global Constraints

- Python 3.10+ (type hints throughout)
- No async Flask — use sync routes; Playwright runs in sync mode
- All user-facing text in Chinese (zh-CN)
- The card system API allows max 31 days per query; fetcher must chunk accordingly
- LLM integration is optional — the app must be fully functional without any LLM configured
- Project root: `BUCT_Card_Report/`
- Run tests: `pytest tests/ -v`
- Run app: `python app.py` (starts Flask on localhost:5000)

## File Structure

```
BUCT_Card_Report/
├── app.py                    # Flask application entry point + routes
├── config.py                 # Configuration (LLM API keys, defaults)
├── requirements.txt          # Dependencies
├── README.md                 # Project documentation
├── fetcher/
│   ├── __init__.py
│   ├── url_parser.py         # Parse campus card URLs, extract openid
│   ├── browser.py            # Playwright-based data fetching
│   └── models.py             # Transaction dataclass
├── analyzer/
│   ├── __init__.py
│   ├── categories.py         # Merchant name → category classification
│   └── stats.py              # Statistical analysis functions
├── reporter/
│   ├── __init__.py
│   ├── renderer.py           # HTML report generation
│   └── templates/
│       └── report.html       # Jinja2 report template with Chart.js
├── llm/
│   ├── __init__.py
│   └── insights.py           # LLM-powered analysis via OpenAI-compatible API
├── static/
│   ├── css/style.css         # Web UI styles
│   └── js/main.js            # Web UI frontend logic (fetch status, show report)
├── templates/
│   └── index.html            # Flask index page (URL input form)
└── tests/
    ├── __init__.py
    ├── test_url_parser.py
    ├── test_categories.py
    ├── test_stats.py
    └── test_renderer.py
```

---

### Task 1: Project Scaffolding

**Files:**
- Create: `BUCT_Card_Report/requirements.txt`
- Create: `BUCT_Card_Report/config.py`
- Create: `BUCT_Card_Report/README.md`
- Create: all `__init__.py` files (fetcher/, analyzer/, reporter/, llm/, tests/)

**Interfaces:**
- Produces: `config.Config` dataclass with all configuration fields
- Produces: `fetcher.models.Transaction` dataclass

- [ ] **Step 1: Create requirements.txt**

```
flask>=3.0
playwright>=1.40
pandas>=2.0
openpyxl>=3.1
openai>=1.0
jinja2>=3.1
pytest>=8.0
```

- [ ] **Step 2: Create config.py**

```python
from dataclasses import dataclass, field
from typing import Optional
import os

@dataclass
class Config:
    # Card system
    card_base_url: str = "https://mcard.buct.edu.cn"
    max_query_days: int = 31

    # LLM (optional)
    llm_api_key: Optional[str] = field(default_factory=lambda: os.environ.get("LLM_API_KEY"))
    llm_base_url: Optional[str] = field(default_factory=lambda: os.environ.get("LLM_BASE_URL"))
    llm_model: str = field(default_factory=lambda: os.environ.get("LLM_MODEL", "deepseek-chat"))

    @property
    def llm_enabled(self) -> bool:
        return bool(self.llm_api_key and self.llm_base_url)
```

- [ ] **Step 3: Create fetcher/models.py**

```python
from dataclasses import dataclass
from datetime import datetime

@dataclass
class Transaction:
    merchant: str
    amount: float
    timestamp: datetime

    @property
    def is_expense(self) -> bool:
        return self.amount < 0

    @property
    def abs_amount(self) -> float:
        return abs(self.amount)
```

- [ ] **Step 4: Create all __init__.py files and README.md**

Each `__init__.py` is empty. README.md:

```markdown
# BUCT_Card_Report

北京化工大学校园卡消费数据分析报告生成器。

## 功能

- 从校园卡系统自动拉取消费流水（支持近10个月数据）
- 内置多维度消费分析（月度趋势、分类统计、商户排名、用餐时段）
- 生成精美的 HTML 可视化报告
- 可选接入大模型（DeepSeek/通义千问/硅基流动）生成个性化洞察

## 快速开始

```bash
pip install -r requirements.txt
playwright install chromium
python app.py
# 打开 http://localhost:5000
```

## 使用方法

1. 在企业微信中打开校园卡页面
2. 复制页面链接（包含 openid 参数）
3. 粘贴到本应用的输入框
4. 等待数据拉取完成，选择分析方式
5. 生成并下载报告

## 可选：大模型增强

设置环境变量即可启用 LLM 个性化分析：

```bash
export LLM_API_KEY="your-api-key"
export LLM_BASE_URL="https://api.deepseek.com/v1"   # DeepSeek
# export LLM_BASE_URL="https://dashscope.aliyuncs.com/compatible-mode/v1"  # 通义千问
# export LLM_BASE_URL="https://api.siliconflow.cn/v1"  # 硅基流动
export LLM_MODEL="deepseek-chat"
```
```

- [ ] **Step 5: Install dependencies and verify**

Run: `pip install -r requirements.txt && playwright install chromium`
Expected: All packages install without errors, `playwright install` downloads Chromium.

- [ ] **Step 6: Commit**

```bash
git init
git add -A
git commit -m "chore: project scaffolding with config, models, and dependencies"
```

---

### Task 2: URL Parser

**Files:**
- Create: `fetcher/url_parser.py`
- Test: `tests/test_url_parser.py`

**Interfaces:**
- Consumes: nothing
- Produces: `parse_card_url(url: str) -> str` — returns openid string, raises ValueError on invalid input

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_url_parser.py
import pytest
from fetcher.url_parser import parse_card_url

def test_parse_homepage_url_with_openid():
    url = "https://mcard.buct.edu.cn/home/openHomePage?openid=28FEDACDA8CED916E321C4C6939BB657"
    assert parse_card_url(url) == "28FEDACDA8CED916E321C4C6939BB657"

def test_parse_selftrade_url_with_openid():
    url = "https://mcard.buct.edu.cn/selftrade/openQueryCardSelfTrade?openid=ABC123&displayflag=1&id=23"
    assert parse_card_url(url) == "ABC123"

def test_parse_url_with_code_returns_error():
    url = "https://mcard.buct.edu.cn/home/openHomePage?code=GTXG1JWiP2CX1iUl&state=123"
    with pytest.raises(ValueError, match="code.*expired"):
        parse_card_url(url)

def test_parse_url_no_params():
    url = "https://mcard.buct.edu.cn/home/openHomePage"
    with pytest.raises(ValueError, match="openid"):
        parse_card_url(url)

def test_parse_invalid_url():
    with pytest.raises(ValueError):
        parse_card_url("not a url at all")

def test_parse_non_buct_domain():
    with pytest.raises(ValueError, match="domain"):
        parse_card_url("https://example.com/home?openid=ABC")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_url_parser.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'fetcher.url_parser'`

- [ ] **Step 3: Implement url_parser.py**

```python
# fetcher/url_parser.py
from urllib.parse import urlparse, parse_qs

ALLOWED_DOMAINS = {"mcard.buct.edu.cn"}

def parse_card_url(url: str) -> str:
    """Extract openid from a BUCT campus card URL.

    Args:
        url: Full URL copied from WeCom campus card page.

    Returns:
        The openid string.

    Raises:
        ValueError: If the URL is invalid, missing openid, or contains
                     only an expired OAuth code.
    """
    try:
        parsed = urlparse(url)
    except Exception:
        raise ValueError(f"Invalid URL: {url}")

    if parsed.hostname not in ALLOWED_DOMAINS:
        raise ValueError(
            f"Unsupported domain '{parsed.hostname}'. "
            f"Expected one of: {ALLOWED_DOMAINS}"
        )

    params = parse_qs(parsed.query)

    if "openid" in params and params["openid"][0]:
        return params["openid"][0]

    if "code" in params:
        raise ValueError(
            "URL contains an OAuth 'code' but no 'openid'. "
            "The code is single-use and likely expired. "
            "Please open the page in WeCom first, then copy the "
            "redirected URL that contains 'openid='."
        )

    raise ValueError(
        "No 'openid' parameter found in URL. "
        "Please copy the full URL from the campus card page in WeCom."
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_url_parser.py -v`
Expected: All 6 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add fetcher/url_parser.py tests/test_url_parser.py
git commit -m "feat: URL parser extracts openid from campus card URLs"
```

---

### Task 3: Merchant Categorization

**Files:**
- Create: `analyzer/categories.py`
- Test: `tests/test_categories.py`

**Interfaces:**
- Consumes: merchant name string
- Produces: `categorize(merchant: str) -> str` — returns category label
- Produces: `ALL_CATEGORIES: list[str]` — all possible category values

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_categories.py
import pytest
from analyzer.categories import categorize, ALL_CATEGORIES

def test_canteen_main():
    assert categorize("玉兰二食堂-快乐烤盘饭") == "餐饮"
    assert categorize("紫竹民族-鸡柳大人") == "餐饮"
    assert categorize("东一基本伙-副食组") == "餐饮"
    assert categorize("紫竹四-营养盖饭") == "餐饮"

def test_beverage():
    assert categorize("紫竹民族-水吧") == "饮品"
    assert categorize("紫竹一-水吧") == "饮品"
    assert categorize("紫竹二基本伙-水吧组") == "饮品"

def test_snacks_fruit():
    assert categorize("餐饮中心甜工社面包房") == "零食/水果"
    assert categorize("餐饮中心昌平校区水果店") == "零食/水果"

def test_recharge():
    assert categorize("微信支付转账充值") == "充值/转账"
    assert categorize("支付宝转账") == "充值/转账"

def test_utilities():
    assert categorize("网络缴费") == "网络缴费"
    assert categorize("东区移动端售电") == "生活服务"

def test_transport():
    assert categorize("交通运输中心手持GPRS消费") == "交通"

def test_medical():
    assert categorize("昌平校医院医疗收费") == "医疗"

def test_bath():
    assert categorize("东区学一公寓浴室") == "浴室/开水"
    assert categorize("东区学一公寓开水") == "浴室/开水"

def test_card_replacement():
    assert categorize("自助补卡校园卡支付卡成本") == "补卡"

def test_unknown_defaults_to_canteen():
    # Most unclassified merchants at BUCT are food stalls
    assert categorize("某个未知商户") == "餐饮"

def test_all_categories_is_nonempty_list():
    assert isinstance(ALL_CATEGORIES, list)
    assert len(ALL_CATEGORIES) >= 8
    assert "餐饮" in ALL_CATEGORIES
    assert "充值/转账" in ALL_CATEGORIES
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_categories.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'analyzer.categories'`

- [ ] **Step 3: Implement categories.py**

```python
# analyzer/categories.py

ALL_CATEGORIES = [
    "餐饮", "饮品", "零食/水果", "充值/转账",
    "网络缴费", "生活服务", "交通", "医疗",
    "浴室/开水", "补卡", "其他",
]

# Rules checked in order — first match wins
_RULES: list[tuple[list[str], str]] = [
    (["充值", "转账"], "充值/转账"),
    (["网络缴费"], "网络缴费"),
    (["浴室", "开水"], "浴室/开水"),
    (["校医院", "医疗"], "医疗"),
    (["交通", "GPRS"], "交通"),
    (["补卡"], "补卡"),
    (["售电"], "生活服务"),
    (["水吧"], "饮品"),
    (["水果", "面包", "甜工社"], "零食/水果"),
]

def categorize(merchant: str) -> str:
    """Classify a BUCT campus card merchant into a spending category.

    Args:
        merchant: Raw merchant name from the card system.

    Returns:
        Category label from ALL_CATEGORIES.
        Defaults to '餐饮' if no specific rule matches,
        since the vast majority of BUCT card transactions are food.
    """
    for keywords, category in _RULES:
        if any(kw in merchant for kw in keywords):
            return category
    return "餐饮"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_categories.py -v`
Expected: All 11 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add analyzer/categories.py tests/test_categories.py
git commit -m "feat: merchant categorization with keyword-based rules"
```

---

### Task 4: Statistical Analysis Engine

**Files:**
- Create: `analyzer/stats.py`
- Test: `tests/test_stats.py`

**Interfaces:**
- Consumes: `list[Transaction]` from `fetcher.models`
- Consumes: `categorize()` from `analyzer.categories`
- Produces: `AnalysisResult` dataclass containing all computed statistics
- Produces: `analyze(transactions: list[Transaction]) -> AnalysisResult`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_stats.py
import pytest
from datetime import datetime
from fetcher.models import Transaction
from analyzer.stats import analyze, AnalysisResult

def _make_transactions():
    return [
        Transaction("玉兰二食堂-快乐烤盘饭", -31.00, datetime(2025, 12, 15, 12, 30)),
        Transaction("微信支付转账充值", 50.00, datetime(2025, 12, 15, 12, 28)),
        Transaction("紫竹民族-鸡柳大人", -14.00, datetime(2025, 12, 14, 18, 45)),
        Transaction("支付宝转账", 20.00, datetime(2025, 12, 14, 18, 40)),
        Transaction("网络缴费", -60.00, datetime(2025, 12, 10, 13, 0)),
        Transaction("东区学一公寓浴室", -1.20, datetime(2025, 12, 10, 22, 30)),
        Transaction("东一基本伙-副食组", -8.25, datetime(2026, 1, 5, 7, 58)),
        Transaction("微信支付转账充值", 15.00, datetime(2026, 1, 5, 7, 55)),
    ]

def test_analyze_returns_analysis_result():
    result = analyze(_make_transactions())
    assert isinstance(result, AnalysisResult)

def test_total_expense():
    result = analyze(_make_transactions())
    assert result.total_expense == pytest.approx(114.45, abs=0.01)

def test_total_recharge():
    result = analyze(_make_transactions())
    assert result.total_recharge == pytest.approx(85.00, abs=0.01)

def test_monthly_breakdown():
    result = analyze(_make_transactions())
    assert len(result.monthly) == 2
    dec = next(m for m in result.monthly if m["month"] == "2025-12")
    assert dec["expense"] == pytest.approx(-106.20, abs=0.01)
    assert dec["recharge"] == pytest.approx(70.00, abs=0.01)
    jan = next(m for m in result.monthly if m["month"] == "2026-01")
    assert jan["expense"] == pytest.approx(-8.25, abs=0.01)

def test_category_breakdown():
    result = analyze(_make_transactions())
    cats = {c["category"]: c["total"] for c in result.categories}
    assert "餐饮" in cats
    assert "充值/转账" in cats  # excluded from expense categories
    assert "网络缴费" in cats

def test_top_merchants():
    result = analyze(_make_transactions())
    assert len(result.top_merchants) > 0
    # Top merchant by expense should be 网络缴费 (60) or 烤盘饭 (31)
    assert result.top_merchants[0]["total"] >= 30

def test_meal_time_distribution():
    result = analyze(_make_transactions())
    total_pct = sum(m["percentage"] for m in result.meal_times)
    assert total_pct == pytest.approx(100.0, abs=1.0)

def test_daily_average():
    result = analyze(_make_transactions())
    assert result.daily_avg_expense > 0

def test_transaction_count():
    result = analyze(_make_transactions())
    assert result.total_count == 8
    assert result.expense_count == 5

def test_empty_transactions():
    result = analyze([])
    assert result.total_expense == 0.0
    assert result.total_recharge == 0.0
    assert result.monthly == []
    assert result.categories == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_stats.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'analyzer.stats'`

- [ ] **Step 3: Implement stats.py**

```python
# analyzer/stats.py
from dataclasses import dataclass, field
from datetime import datetime
from collections import defaultdict
from fetcher.models import Transaction
from analyzer.categories import categorize

@dataclass
class AnalysisResult:
    total_expense: float = 0.0
    total_recharge: float = 0.0
    total_count: int = 0
    expense_count: int = 0
    daily_avg_expense: float = 0.0
    monthly: list[dict] = field(default_factory=list)
    categories: list[dict] = field(default_factory=list)
    top_merchants: list[dict] = field(default_factory=list)
    meal_times: list[dict] = field(default_factory=list)
    date_range: tuple[datetime, datetime] | None = None

def analyze(transactions: list[Transaction]) -> AnalysisResult:
    """Compute comprehensive statistics from transaction data.

    Args:
        transactions: List of Transaction objects.

    Returns:
        AnalysisResult with all computed statistics.
    """
    if not transactions:
        return AnalysisResult()

    result = AnalysisResult()
    result.total_count = len(transactions)

    expenses = [t for t in transactions if t.is_expense]
    recharges = [t for t in transactions if not t.is_expense]

    result.expense_count = len(expenses)
    result.total_expense = round(sum(t.abs_amount for t in expenses), 2)
    result.total_recharge = round(sum(t.amount for t in recharges), 2)

    timestamps = [t.timestamp for t in transactions]
    result.date_range = (min(timestamps), max(timestamps))
    days_span = max((result.date_range[1] - result.date_range[0]).days, 1)
    result.daily_avg_expense = round(result.total_expense / days_span, 2)

    # Monthly breakdown
    monthly_data: dict[str, dict] = defaultdict(lambda: {"expense": 0.0, "recharge": 0.0, "count": 0})
    for t in transactions:
        key = t.timestamp.strftime("%Y-%m")
        monthly_data[key]["count"] += 1
        if t.is_expense:
            monthly_data[key]["expense"] += t.amount  # negative
        else:
            monthly_data[key]["recharge"] += t.amount
    result.monthly = sorted(
        [{"month": k, "expense": round(v["expense"], 2), "recharge": round(v["recharge"], 2), "count": v["count"]}
         for k, v in monthly_data.items()],
        key=lambda x: x["month"]
    )

    # Category breakdown (expenses only, excluding 充值/转账)
    cat_data: dict[str, dict] = defaultdict(lambda: {"total": 0.0, "count": 0})
    for t in expenses:
        cat = categorize(t.merchant)
        if cat != "充值/转账":
            cat_data[cat]["total"] += t.abs_amount
            cat_data[cat]["count"] += 1
    total_cat = sum(v["total"] for v in cat_data.values()) or 1.0
    result.categories = sorted(
        [{"category": k, "total": round(v["total"], 2), "count": v["count"],
          "avg": round(v["total"] / v["count"], 2),
          "percentage": round(v["total"] / total_cat * 100, 1)}
         for k, v in cat_data.items()],
        key=lambda x: x["total"], reverse=True
    )

    # Top merchants (expenses only)
    mer_data: dict[str, dict] = defaultdict(lambda: {"total": 0.0, "count": 0})
    for t in expenses:
        mer_data[t.merchant]["total"] += t.abs_amount
        mer_data[t.merchant]["count"] += 1
    result.top_merchants = sorted(
        [{"merchant": k, "total": round(v["total"], 2), "count": v["count"]}
         for k, v in mer_data.items()],
        key=lambda x: x["total"], reverse=True
    )[:15]

    # Meal time distribution (expenses during meal-relevant hours)
    meal_bins = {"早餐 (6-10)": 0.0, "午餐 (10-14)": 0.0, "晚餐 (14-20)": 0.0, "夜宵 (20-6)": 0.0}
    for t in expenses:
        h = t.timestamp.hour
        if 6 <= h < 10:
            meal_bins["早餐 (6-10)"] += t.abs_amount
        elif 10 <= h < 14:
            meal_bins["午餐 (10-14)"] += t.abs_amount
        elif 14 <= h < 20:
            meal_bins["晚餐 (14-20)"] += t.abs_amount
        else:
            meal_bins["夜宵 (20-6)"] += t.abs_amount
    meal_total = sum(meal_bins.values()) or 1.0
    result.meal_times = [
        {"period": k, "amount": round(v, 2), "percentage": round(v / meal_total * 100, 1)}
        for k, v in meal_bins.items()
    ]

    return result
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_stats.py -v`
Expected: All 9 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add analyzer/stats.py tests/test_stats.py
git commit -m "feat: statistical analysis engine with monthly/category/merchant/meal-time stats"
```

---

### Task 5: Playwright Data Fetcher

**Files:**
- Create: `fetcher/browser.py`

**Interfaces:**
- Consumes: `parse_card_url()` from `fetcher.url_parser`
- Consumes: `Transaction` from `fetcher.models`
- Produces: `fetch_transactions(openid: str, start_date: str, end_date: str, on_progress: Callable | None) -> list[Transaction]`

**Note:** This task has no automated tests because Playwright requires a real browser and network. Verify manually with the integration test in Task 8.

- [ ] **Step 1: Implement browser.py**

```python
# fetcher/browser.py
import time
import json
import logging
from datetime import datetime, timedelta
from typing import Callable, Optional
from playwright.sync_api import sync_playwright, Page
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
(beginTime, endTime) => {
    document.getElementById('beginTime').value = beginTime;
    document.getElementById('endTime').value = endTime;
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
            page.evaluate(TRIGGER_QUERY_JS, begin_str, end_str)
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
```

- [ ] **Step 2: Quick syntax check**

Run: `python -c "from fetcher.browser import fetch_transactions; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add fetcher/browser.py
git commit -m "feat: Playwright-based transaction fetcher with batch querying"
```

---

### Task 6: HTML Report Renderer

**Files:**
- Create: `reporter/renderer.py`
- Create: `reporter/templates/report.html`
- Test: `tests/test_renderer.py`

**Interfaces:**
- Consumes: `AnalysisResult` from `analyzer.stats`
- Consumes: `list[Transaction]` from `fetcher.models`
- Produces: `render_report(analysis: AnalysisResult, transactions: list[Transaction], llm_insight: str | None = None) -> str` — returns complete HTML string

- [ ] **Step 1: Write the failing test**

```python
# tests/test_renderer.py
import pytest
from datetime import datetime
from fetcher.models import Transaction
from analyzer.stats import analyze, AnalysisResult
from reporter.renderer import render_report

def _sample_data():
    txs = [
        Transaction("玉兰二食堂-快乐烤盘饭", -31.00, datetime(2025, 12, 15, 12, 30)),
        Transaction("微信支付转账充值", 50.00, datetime(2025, 12, 15, 12, 28)),
        Transaction("紫竹民族-鸡柳大人", -14.00, datetime(2025, 12, 14, 18, 45)),
    ]
    return txs, analyze(txs)

def test_render_returns_html_string():
    txs, analysis = _sample_data()
    html = render_report(analysis, txs)
    assert isinstance(html, str)
    assert "<!DOCTYPE html>" in html or "<html" in html

def test_render_contains_chart_containers():
    txs, analysis = _sample_data()
    html = render_report(analysis, txs)
    assert "Chart.js" in html or "chart.js" in html or "Chart" in html

def test_render_contains_kpi_values():
    txs, analysis = _sample_data()
    html = render_report(analysis, txs)
    assert "45.00" in html or "45" in html  # total expense

def test_render_with_llm_insight():
    txs, analysis = _sample_data()
    html = render_report(analysis, txs, llm_insight="你是一个节省的人")
    assert "你是一个节省的人" in html

def test_render_without_llm_insight():
    txs, analysis = _sample_data()
    html = render_report(analysis, txs, llm_insight=None)
    assert isinstance(html, str)
    assert len(html) > 500

def test_render_empty_data():
    empty = AnalysisResult()
    html = render_report(empty, [])
    assert isinstance(html, str)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_renderer.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'reporter.renderer'`

- [ ] **Step 3: Create the Jinja2 report template**

Create `reporter/templates/report.html` — a self-contained HTML file with embedded Chart.js. The template receives `analysis` (AnalysisResult), `transactions` (list), `llm_insight` (str|None), and `generated_at` (str).

This template should include:
- KPI cards showing total_expense, total_recharge, daily_avg_expense, expense_count
- Monthly bar chart (Chart.js) using `analysis.monthly` data
- Category doughnut chart using `analysis.categories` data
- Top 10 merchants horizontal bar chart using `analysis.top_merchants`
- Meal time distribution section
- Optional LLM insight section (shown only if `llm_insight` is provided)
- Responsive design, Chinese labels, professional color scheme

The template should serialize `analysis` data as JSON in a `<script>` block and use Chart.js to render charts client-side.

```html
{# reporter/templates/report.html #}
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>BUCT 校园卡消费报告</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js"></script>
<style>
:root{--primary:#2F5496;--accent:#E74C3C;--green:#27AE60;--bg:#F5F7FA;--card:#FFF;--text:#2C3E50;--muted:#95A5A6;--border:#E8EEF7}
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,'Segoe UI','PingFang SC','Microsoft YaHei',sans-serif;background:var(--bg);color:var(--text);line-height:1.6}
.container{max-width:960px;margin:0 auto;padding:24px 16px}
.header{text-align:center;padding:40px 0 24px}
.header h1{font-size:28px;color:var(--primary)}
.header p{color:var(--muted);font-size:14px;margin-top:8px}
.kpi-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin-bottom:32px}
.kpi-card{background:var(--card);border-radius:12px;padding:20px;text-align:center;border:1px solid var(--border)}
.kpi-card .label{font-size:12px;color:var(--muted)}
.kpi-card .value{font-size:28px;font-weight:700;color:var(--primary);margin:8px 0}
.kpi-card .sub{font-size:12px;color:var(--muted)}
.section{background:var(--card);border-radius:12px;padding:24px;margin-bottom:24px;border:1px solid var(--border)}
.section h2{font-size:18px;color:var(--primary);margin-bottom:16px;padding-bottom:12px;border-bottom:2px solid var(--border)}
.chart-container{position:relative;height:320px;margin:16px 0}
.chart-row{display:grid;grid-template-columns:1fr 1fr;gap:24px}
.merchant-bar{margin:8px 0}
.merchant-bar .name{font-size:13px;margin-bottom:4px;display:flex;justify-content:space-between}
.merchant-bar .bar-bg{height:8px;background:var(--border);border-radius:4px;overflow:hidden}
.merchant-bar .bar-fill{height:100%;border-radius:4px;background:linear-gradient(90deg,var(--primary),#5B8DEF)}
.insight-box{background:#F0F4FF;border-radius:8px;padding:16px;margin-top:16px;border-left:4px solid var(--primary);white-space:pre-wrap;font-size:14px;line-height:1.8}
.meal-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;text-align:center}
.meal-item{padding:16px 8px;border-radius:8px;background:var(--bg)}
.meal-item .pct{font-size:20px;font-weight:700;color:var(--primary);margin:8px 0}
.meal-item .desc{font-size:12px;color:var(--muted)}
.footer{text-align:center;padding:24px 0;color:var(--muted);font-size:12px}
@media(max-width:640px){.kpi-grid{grid-template-columns:repeat(2,1fr)}.chart-row{grid-template-columns:1fr}.meal-grid{grid-template-columns:repeat(2,1fr)}}
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <h1>BUCT 校园卡消费报告</h1>
    <p>数据周期：{{ date_start }} ~ {{ date_end }} | 共 {{ analysis.total_count }} 笔交易 | 生成时间：{{ generated_at }}</p>
  </div>

  <div class="kpi-grid">
    <div class="kpi-card">
      <div class="label">总消费</div>
      <div class="value">¥{{ "%.0f"|format(analysis.total_expense) }}</div>
      <div class="sub">{{ analysis.expense_count }} 笔消费</div>
    </div>
    <div class="kpi-card">
      <div class="label">总充值</div>
      <div class="value">¥{{ "%.0f"|format(analysis.total_recharge) }}</div>
    </div>
    <div class="kpi-card">
      <div class="label">日均消费</div>
      <div class="value">¥{{ "%.1f"|format(analysis.daily_avg_expense) }}</div>
    </div>
    <div class="kpi-card">
      <div class="label">单笔均价</div>
      <div class="value">¥{{ "%.1f"|format(analysis.total_expense / analysis.expense_count if analysis.expense_count else 0) }}</div>
    </div>
  </div>

  <div class="section">
    <h2>月度消费趋势</h2>
    <div class="chart-container"><canvas id="monthlyChart"></canvas></div>
  </div>

  <div class="chart-row">
    <div class="section">
      <h2>消费分类占比</h2>
      <div class="chart-container"><canvas id="catChart"></canvas></div>
    </div>
    <div class="section">
      <h2>用餐时段分布</h2>
      <div class="meal-grid">
        {% for m in analysis.meal_times %}
        <div class="meal-item">
          <div class="pct">{{ "%.0f"|format(m.percentage) }}%</div>
          <div class="desc">{{ m.period }}</div>
        </div>
        {% endfor %}
      </div>
    </div>
  </div>

  <div class="section">
    <h2>TOP {{ analysis.top_merchants|length }} 消费商户</h2>
    <div id="merchantList"></div>
  </div>

  {% if llm_insight %}
  <div class="section">
    <h2>AI 个性化洞察</h2>
    <div class="insight-box">{{ llm_insight }}</div>
  </div>
  {% endif %}

  <div class="footer">
    <p>Generated by BUCT_Card_Report · 数据来源: mcard.buct.edu.cn</p>
  </div>
</div>

<script>
const monthly = {{ analysis.monthly | tojson }};
const categories = {{ analysis.categories | tojson }};
const topMerchants = {{ analysis.top_merchants | tojson }};

new Chart(document.getElementById('monthlyChart'), {
  type: 'bar',
  data: {
    labels: monthly.map(m => m.month),
    datasets: [
      { label: '消费', data: monthly.map(m => Math.abs(m.expense)), backgroundColor: 'rgba(231,76,60,0.7)', borderRadius: 6 },
      { label: '充值', data: monthly.map(m => m.recharge), backgroundColor: 'rgba(39,174,96,0.7)', borderRadius: 6 }
    ]
  },
  options: { responsive: true, maintainAspectRatio: false, scales: { y: { beginAtZero: true, ticks: { callback: v => '¥' + v } } } }
});

const COLORS = ['#2F5496','#E74C3C','#F39C12','#3498DB','#1ABC9C','#9B59B6','#E67E22','#2ECC71','#95A5A6','#C0392B','#16A085'];
new Chart(document.getElementById('catChart'), {
  type: 'doughnut',
  data: {
    labels: categories.map(c => c.category),
    datasets: [{ data: categories.map(c => c.total), backgroundColor: COLORS, borderWidth: 2, borderColor: '#fff' }]
  },
  options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: 'right' } } }
});

const maxAmt = topMerchants.length > 0 ? topMerchants[0].total : 1;
const list = document.getElementById('merchantList');
topMerchants.slice(0, 10).forEach((m, i) => {
  const pct = (m.total / maxAmt * 100).toFixed(0);
  list.innerHTML += '<div class="merchant-bar"><div class="name"><span>' + (i+1) + '. ' + m.merchant + '</span><span>¥' + m.total + ' (' + m.count + '次)</span></div><div class="bar-bg"><div class="bar-fill" style="width:' + pct + '%"></div></div></div>';
});
</script>
</body>
</html>
```

- [ ] **Step 4: Implement renderer.py**

```python
# reporter/renderer.py
from datetime import datetime
from pathlib import Path
from jinja2 import Environment, FileSystemLoader
from analyzer.stats import AnalysisResult
from fetcher.models import Transaction

_TEMPLATE_DIR = Path(__file__).parent / "templates"
_env = Environment(loader=FileSystemLoader(str(_TEMPLATE_DIR)))

def render_report(
    analysis: AnalysisResult,
    transactions: list[Transaction],
    llm_insight: str | None = None,
) -> str:
    """Render an HTML report from analysis results.

    Args:
        analysis: Computed AnalysisResult.
        transactions: Raw transaction list (for future use).
        llm_insight: Optional LLM-generated text to include.

    Returns:
        Complete self-contained HTML string.
    """
    template = _env.get_template("report.html")

    date_start = analysis.date_range[0].strftime("%Y-%m-%d") if analysis.date_range else "N/A"
    date_end = analysis.date_range[1].strftime("%Y-%m-%d") if analysis.date_range else "N/A"

    return template.render(
        analysis=analysis,
        transactions=transactions,
        llm_insight=llm_insight,
        date_start=date_start,
        date_end=date_end,
        generated_at=datetime.now().strftime("%Y-%m-%d %H:%M"),
    )
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_renderer.py -v`
Expected: All 6 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add reporter/ tests/test_renderer.py
git commit -m "feat: HTML report renderer with Chart.js visualizations"
```

---

### Task 7: LLM Insights Module

**Files:**
- Create: `llm/insights.py`

**Interfaces:**
- Consumes: `AnalysisResult` from `analyzer.stats`
- Consumes: `Config` from `config`
- Produces: `generate_insight(analysis: AnalysisResult, config: Config) -> str | None` — returns LLM-generated text, or None if LLM is disabled/errors

- [ ] **Step 1: Implement insights.py**

```python
# llm/insights.py
import logging
from openai import OpenAI
from analyzer.stats import AnalysisResult
from config import Config

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """你是一个校园卡消费分析助手。根据用户提供的消费统计数据，用轻松有趣的语气生成个性化消费洞察。
要求：
- 300字以内
- 指出消费特点和趋势
- 给出1-2条实用建议
- 可以适当用emoji
- 使用中文"""

def _build_prompt(analysis: AnalysisResult) -> str:
    parts = [f"消费数据概览（共{analysis.total_count}笔交易）："]
    parts.append(f"- 总消费：¥{analysis.total_expense}，{analysis.expense_count}笔")
    parts.append(f"- 总充值：¥{analysis.total_recharge}")
    parts.append(f"- 日均消费：¥{analysis.daily_avg_expense}")

    if analysis.date_range:
        parts.append(f"- 时间跨度：{analysis.date_range[0].strftime('%Y-%m-%d')} ~ {analysis.date_range[1].strftime('%Y-%m-%d')}")

    if analysis.monthly:
        parts.append("\n月度消费：")
        for m in analysis.monthly:
            parts.append(f"  {m['month']}：消费¥{abs(m['expense']):.0f}，充值¥{m['recharge']:.0f}")

    if analysis.categories:
        parts.append("\n消费分类（按金额排序）：")
        for c in analysis.categories[:5]:
            parts.append(f"  {c['category']}：¥{c['total']}（{c['count']}笔，占{c['percentage']}%）")

    if analysis.top_merchants:
        parts.append("\n消费最多的商户：")
        for m in analysis.top_merchants[:5]:
            parts.append(f"  {m['merchant']}：¥{m['total']}（{m['count']}次）")

    if analysis.meal_times:
        parts.append("\n用餐时段分布：")
        for m in analysis.meal_times:
            parts.append(f"  {m['period']}：{m['percentage']}%")

    return "\n".join(parts)

def generate_insight(analysis: AnalysisResult, config: Config) -> str | None:
    """Generate personalized insight using an LLM.

    Args:
        analysis: Computed analysis results.
        config: App config with LLM API settings.

    Returns:
        LLM-generated insight text, or None if disabled/error.
    """
    if not config.llm_enabled:
        logger.info("LLM not configured, skipping insight generation")
        return None

    try:
        client = OpenAI(
            api_key=config.llm_api_key,
            base_url=config.llm_base_url,
        )
        prompt = _build_prompt(analysis)
        response = client.chat.completions.create(
            model=config.llm_model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"请分析以下校园卡消费数据并给出洞察：\n\n{prompt}"},
            ],
            max_tokens=800,
            temperature=0.7,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"LLM insight generation failed: {e}")
        return None
```

- [ ] **Step 2: Verify import works**

Run: `python -c "from llm.insights import generate_insight; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add llm/insights.py
git commit -m "feat: LLM insights module with OpenAI-compatible API support"
```

---

### Task 8: Flask Web Application

**Files:**
- Create: `app.py`
- Create: `templates/index.html`
- Create: `static/css/style.css`
- Create: `static/js/main.js`

**Interfaces:**
- Consumes: everything from previous tasks
- Produces: running web server on localhost:5000

- [ ] **Step 1: Create the Flask index page template**

`templates/index.html` — A clean single-page UI with:
- Title and description
- URL input form (textarea for pasting the campus card URL)
- Date range pickers (start/end date, defaulting to last 10 months)
- "开始分析" button
- Progress indicator area
- Options panel (shown after data fetch): checkboxes for "基础分析" (always on), "LLM 增强分析" (if available)
- Report preview / download area

- [ ] **Step 2: Create static CSS**

`static/css/style.css` — Minimal clean styling for the index page.

- [ ] **Step 3: Create frontend JS**

`static/js/main.js` — Handles:
- Form submission → POST to `/api/fetch`
- Polling `/api/status` for progress updates
- When complete, show options panel
- "生成报告" → POST to `/api/report`
- Display report in iframe or open in new tab

- [ ] **Step 4: Implement app.py**

```python
# app.py
import json
import logging
import threading
from pathlib import Path
from flask import Flask, render_template, request, jsonify, send_file
from config import Config
from fetcher.url_parser import parse_card_url
from fetcher.browser import fetch_transactions
from analyzer.stats import analyze
from reporter.renderer import render_report
from llm.insights import generate_insight

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

app = Flask(__name__)
config = Config()

# In-memory state (single-user app)
_state = {
    "status": "idle",       # idle | fetching | done | error
    "message": "",
    "count": 0,
    "transactions": None,
    "analysis": None,
}

@app.route("/")
def index():
    return render_template("index.html", llm_available=config.llm_enabled)

@app.route("/api/fetch", methods=["POST"])
def api_fetch():
    data = request.get_json()
    url = data.get("url", "").strip()
    start_date = data.get("start_date", "2025-09-01")
    end_date = data.get("end_date", None)

    try:
        openid = parse_card_url(url)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    _state["status"] = "fetching"
    _state["message"] = "正在启动浏览器..."
    _state["count"] = 0

    def _run():
        try:
            def on_progress(msg, count):
                _state["message"] = msg
                _state["count"] = count

            txs = fetch_transactions(openid, start_date, end_date, on_progress)
            _state["transactions"] = txs
            _state["analysis"] = analyze(txs)
            _state["status"] = "done"
            _state["message"] = f"成功获取 {len(txs)} 条记录"
        except Exception as e:
            logger.exception("Fetch failed")
            _state["status"] = "error"
            _state["message"] = f"获取失败: {e}"

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()

    return jsonify({"status": "started"})

@app.route("/api/status")
def api_status():
    return jsonify({
        "status": _state["status"],
        "message": _state["message"],
        "count": _state["count"],
    })

@app.route("/api/report", methods=["POST"])
def api_report():
    if _state["status"] != "done" or not _state["analysis"]:
        return jsonify({"error": "No data available"}), 400

    data = request.get_json() or {}
    use_llm = data.get("use_llm", False)

    llm_insight = None
    if use_llm and config.llm_enabled:
        llm_insight = generate_insight(_state["analysis"], config)

    html = render_report(_state["analysis"], _state["transactions"], llm_insight)

    output_path = Path("output_report.html")
    output_path.write_text(html, encoding="utf-8")

    return jsonify({"html": html})

@app.route("/api/report/download")
def api_download():
    path = Path("output_report.html")
    if not path.exists():
        return "No report available", 404
    return send_file(path, mimetype="text/html", as_attachment=True,
                     download_name="BUCT_校园卡消费报告.html")

if __name__ == "__main__":
    app.run(debug=True, port=5000)
```

- [ ] **Step 5: Manual integration test**

Run: `python app.py`
Open: http://localhost:5000
Steps:
1. Paste a valid campus card URL with openid
2. Click "开始分析"
3. Watch progress update
4. When done, click "生成报告"
5. Verify the report displays correctly with charts

- [ ] **Step 6: Commit**

```bash
git add app.py templates/ static/
git commit -m "feat: Flask web app with data fetch, analysis, and report generation"
```

---

### Task 9: Final Polish and README

**Files:**
- Modify: `README.md`
- Create: `.gitignore`

- [ ] **Step 1: Create .gitignore**

```
__pycache__/
*.pyc
.env
output_report.html
*.egg-info/
dist/
.venv/
```

- [ ] **Step 2: Update README.md with full documentation**

Include: screenshots, architecture diagram (ASCII), API reference for key functions, contributing guide, license placeholder.

- [ ] **Step 3: Run full test suite**

Run: `pytest tests/ -v`
Expected: All tests pass.

- [ ] **Step 4: Final commit**

```bash
git add -A
git commit -m "docs: complete README with usage guide and project documentation"
```
