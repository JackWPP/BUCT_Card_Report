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
