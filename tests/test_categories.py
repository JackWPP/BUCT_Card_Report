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
