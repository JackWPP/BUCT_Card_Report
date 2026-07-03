"""Tests for the CSV import endpoint."""
import io
import json

import pytest

from app import app, _state, _state_lock


@pytest.fixture
def client():
    return app.test_client()


@pytest.fixture
def reset_state():
    """Wipe _state so a successful import can be observed cleanly."""
    with _state_lock:
        _state["transactions"] = None
        _state["analysis"] = None
        _state["status"] = "idle"
    yield
    with _state_lock:
        _state["transactions"] = None
        _state["analysis"] = None
        _state["status"] = "idle"


def _post_csv(client, body: bytes, filename: str = "test.csv"):
    return client.post(
        "/api/transactions/import",
        data={"file": (io.BytesIO(body), filename)},
        content_type="multipart/form-data",
    )


def test_import_rejects_no_file(client):
    r = client.post("/api/transactions/import", data={}, content_type="multipart/form-data")
    assert r.status_code == 400
    assert "error" in r.get_json()


def test_import_rejects_non_csv(client):
    r = _post_csv(client, b"hello", filename="notes.txt")
    assert r.status_code == 400
    assert "csv" in r.get_json()["error"].lower()


def test_import_happy_path(client, reset_state):
    """A well-formed CSV (round-trip of the export format) must load the
    full pipeline: _state gets transactions + analysis."""
    body = (
        "交易时间,商户名称,金额(元),类型,绝对金额(元),分类\n"
        "2025-12-15 12:30:00,玉兰食堂-烤盘饭,-31.50,消费,31.50,餐饮\n"
        "2025-12-15 09:00:00,微信充值,100.00,充值,100.00,充值/转账\n"
        "2025-12-14 18:45:00,紫竹-鸡柳,-14.00,消费,14.00,餐饮\n"
    ).encode("utf-8")
    r = _post_csv(client, body)
    assert r.status_code == 200
    data = r.get_json()
    assert data["count"] == 3
    assert data["skipped_rows"] == 0
    assert data["date_start"] == "2025-12-14"
    assert data["date_end"] == "2025-12-15"
    with _state_lock:
        assert len(_state["transactions"]) == 3
        assert _state["status"] == "done"
        assert _state["analysis"] is not None
        assert _state["analysis"].total_count == 3


def test_import_strips_utf8_bom(client, reset_state):
    """Excel-issued CSVs start with a BOM; the importer must strip it."""
    body = b"\xef\xbb\xbf" + (
        "交易时间,商户名称,金额(元)\n"
        "2025-12-15 12:30:00,食堂,-10\n"
    ).encode("utf-8")
    r = _post_csv(client, body)
    assert r.status_code == 200
    assert r.get_json()["count"] == 1


def test_import_missing_required_column(client, reset_state):
    """A CSV with no amount column must be rejected with 400 + helpful info."""
    body = "时间,商户\n2025-12-15,食堂\n".encode("utf-8")
    r = _post_csv(client, body)
    assert r.status_code == 400
    data = r.get_json()
    assert "amount" in str(data) or "金额" in str(data)
    assert "found_columns" in data


def test_import_alias_columns(client, reset_state):
    """Columns named in English/alias form must be recognized."""
    body = (
        "Date,Merchant,Amount\n"
        "2025-12-15 12:00,Test Merchant,-10.50\n"
        "2025-12-15 13:00,Another,5.00\n"
    ).encode("utf-8")
    r = _post_csv(client, body)
    assert r.status_code == 200
    assert r.get_json()["count"] == 2


def test_import_strips_currency_symbols(client, reset_state):
    """Amounts like '¥-12.50' or '12.50元' should parse, and quoted
    thousands separators inside a single cell should be respected."""
    body = (
        "交易时间,商户名称,金额\n"
        "2025-12-15 12:00,食堂1,¥-12.50\n"
        "2025-12-15 13:00,食堂2,12.50元\n"
        '2025-12-15 14:00,食堂3,"-1,234.50"\n'  # thousands separator (quoted)
    ).encode("utf-8")
    r = _post_csv(client, body)
    assert r.status_code == 200
    with _state_lock:
        amounts = [t.amount for t in _state["transactions"]]
    assert amounts == [-12.5, 12.5, -1234.5]


def test_import_alternative_time_formats(client, reset_state):
    """A handful of common time formats should all parse."""
    body = (
        "交易时间,商户名称,金额\n"
        "2025-12-15 12:30:00,A,-10\n"
        "2025-12-15T12:30:00,B,-10\n"
        "2025-12-15,C,-10\n"
        "2025/12/15 12:30,D,-10\n"
    ).encode("utf-8")
    r = _post_csv(client, body)
    assert r.status_code == 200
    assert r.get_json()["count"] == 4


def test_import_skips_malformed_rows(client, reset_state):
    """Rows that can't be parsed must be skipped, not abort the whole import."""
    body = (
        "交易时间,商户名称,金额\n"
        "2025-12-15 12:00,Good,-10\n"
        "not-a-date,Bad Row,abc\n"
        "2025-12-15 13:00,Also Good,-20\n"
    ).encode("utf-8")
    r = _post_csv(client, body)
    assert r.status_code == 200
    data = r.get_json()
    assert data["count"] == 2
    assert data["skipped_rows"] == 1


def test_import_rejects_all_bad_rows(client, reset_state):
    """If every row is bad, return 400 rather than an empty success."""
    body = "交易时间,商户名称,金额\nnot-a-date,x,y\n".encode("utf-8")
    r = _post_csv(client, body)
    assert r.status_code == 400


def test_import_fills_analysis(client, reset_state):
    """The analyze() pipeline must run after import so the report can be
    generated without an extra fetch step."""
    body = (
        "交易时间,商户名称,金额\n"
        "2025-12-15 12:00,玉兰食堂-烤盘饭,-31.00\n"
        "2025-12-15 13:00,微信充值,100.00\n"
    ).encode("utf-8")
    r = _post_csv(client, body)
    assert r.status_code == 200
    with _state_lock:
        a = _state["analysis"]
    assert a is not None
    assert a.total_expense == 31.0
    assert a.total_recharge == 100.0
    assert a.expense_count == 1
    # Categories should include the default-餐饮 for the unnamed merchant
    cats = {c["category"] for c in a.categories}
    assert "餐饮" in cats
    assert "充值/转账" in cats
