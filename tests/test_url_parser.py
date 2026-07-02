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
