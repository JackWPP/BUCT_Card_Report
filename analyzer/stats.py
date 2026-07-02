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
    monthly_data: dict[str, dict] = defaultdict(
        lambda: {"expense": 0.0, "recharge": 0.0, "count": 0}
    )
    for t in transactions:
        key = t.timestamp.strftime("%Y-%m")
        monthly_data[key]["count"] += 1
        if t.is_expense:
            monthly_data[key]["expense"] += t.amount  # negative
        else:
            monthly_data[key]["recharge"] += t.amount
    result.monthly = sorted(
        [
            {
                "month": k,
                "expense": round(v["expense"], 2),
                "recharge": round(v["recharge"], 2),
                "count": v["count"],
            }
            for k, v in monthly_data.items()
        ],
        key=lambda x: x["month"],
    )

    # Category breakdown (all transactions)
    cat_data: dict[str, dict] = defaultdict(lambda: {"total": 0.0, "count": 0})
    for t in transactions:
        cat = categorize(t.merchant)
        cat_data[cat]["total"] += t.abs_amount
        cat_data[cat]["count"] += 1
    total_cat = sum(v["total"] for v in cat_data.values()) or 1.0
    result.categories = sorted(
        [
            {
                "category": k,
                "total": round(v["total"], 2),
                "count": v["count"],
                "avg": round(v["total"] / v["count"], 2),
                "percentage": round(v["total"] / total_cat * 100, 1),
            }
            for k, v in cat_data.items()
        ],
        key=lambda x: x["total"],
        reverse=True,
    )

    # Top merchants (expenses only)
    mer_data: dict[str, dict] = defaultdict(lambda: {"total": 0.0, "count": 0})
    for t in expenses:
        mer_data[t.merchant]["total"] += t.abs_amount
        mer_data[t.merchant]["count"] += 1
    result.top_merchants = sorted(
        [
            {"merchant": k, "total": round(v["total"], 2), "count": v["count"]}
            for k, v in mer_data.items()
        ],
        key=lambda x: x["total"],
        reverse=True,
    )[:15]

    # Meal time distribution (expenses during meal-relevant hours)
    meal_bins = {
        "早餐 (6-10)": 0.0,
        "午餐 (10-14)": 0.0,
        "晚餐 (14-20)": 0.0,
        "夜宵 (20-6)": 0.0,
    }
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
        {
            "period": k,
            "amount": round(v, 2),
            "percentage": round(v / meal_total * 100, 1),
        }
        for k, v in meal_bins.items()
    ]

    return result
