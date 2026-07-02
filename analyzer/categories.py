# analyzer/categories.py

ALL_CATEGORIES = [
    "餐饮", "饮品", "零食/水果", "充值/转账",
    "网络缴费", "生活服务", "交通", "医疗",
    "浴室/开水", "补卡",
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
