"""Tests for the transaction export endpoint (CSV / XLSX)."""
import io
import zipfile
from datetime import datetime

import pytest

from app import app, _state, _state_lock
from fetcher.models import Transaction


@pytest.fixture
def client():
    return app.test_client()


@pytest.fixture
def sample_txs():
    return [
        Transaction("玉兰食堂-烤盘饭", -31.00, datetime(2025, 12, 15, 12, 30)),
        Transaction("微信充值", 100.00, datetime(2025, 12, 15, 9, 0)),
        Transaction("紫竹-鸡柳", -14.00, datetime(2025, 12, 14, 18, 45)),
        Transaction("浴室", -2.00, datetime(2025, 12, 13, 22, 0)),
    ]


@pytest.fixture
def with_transactions(sample_txs):
    """Inject sample transactions into the app's in-memory state for the test."""
    with _state_lock:
        _state["transactions"] = sample_txs
        _state["analysis"] = None
        _state["status"] = "done"
    yield
    with _state_lock:
        _state["transactions"] = None
        _state["analysis"] = None
        _state["status"] = "idle"


def test_export_returns_400_when_no_data(client):
    r = client.get("/api/transactions/export?format=csv")
    assert r.status_code == 400
    assert "error" in r.get_json()


def test_export_unsupported_format_400(client, with_transactions):
    r = client.get("/api/transactions/export?format=xml")
    assert r.status_code == 400
    assert "error" in r.get_json()


def test_export_default_format_is_csv(client, with_transactions):
    r = client.get("/api/transactions/export")
    assert r.status_code == 200
    assert "text/csv" in r.mimetype


def test_export_csv_content(client, with_transactions):
    r = client.get("/api/transactions/export?format=csv")
    assert r.status_code == 200
    body = r.data
    # UTF-8 BOM so Excel on Windows opens Chinese as text
    assert body.startswith(b"\xef\xbb\xbf")
    text = body.decode("utf-8-sig")
    lines = text.strip().split("\n")
    # 1 header + 4 data rows
    assert len(lines) == 5
    # Header
    assert "交易时间" in lines[0]
    assert "商户名称" in lines[0]
    assert "分类" in lines[0]
    # Data row sanity-check
    assert "玉兰食堂" in lines[1]
    assert "消费" in lines[1]
    assert "餐饮" in lines[1]
    # Recharge row
    assert "微信充值" in lines[2]
    assert "充值" in lines[2]
    assert "充值/转账" in lines[2]
    # Filename includes the date range
    assert "20251213" in r.headers["Content-Disposition"]
    assert "20251215" in r.headers["Content-Disposition"]


def test_export_xlsx_content(client, with_transactions):
    r = client.get("/api/transactions/export?format=xlsx")
    assert r.status_code == 200
    assert "spreadsheetml" in r.mimetype
    # Content-Disposition may carry both filename= (ASCII fallback) and
    # filename*= (RFC 5987 UTF-8) — just check the extension is there.
    cd = r.headers["Content-Disposition"]
    assert ".xlsx" in cd
    assert "attachment" in cd

    # XLSX is a zip archive — open and verify
    zf = zipfile.ZipFile(io.BytesIO(r.data))
    names = zf.namelist()
    assert "xl/workbook.xml" in names
    assert "xl/worksheets/sheet1.xml" in names

    if "xl/sharedStrings.xml" in names:
        ss_xml = zf.read("xl/sharedStrings.xml").decode("utf-8")
        assert "玉兰食堂" in ss_xml
        assert "微信充值" in ss_xml
    sheet_xml = zf.read("xl/worksheets/sheet1.xml").decode("utf-8")
    # 5 rows: 1 header + 4 data
    assert sheet_xml.count("<row ") == 5


def test_export_xlsx_handles_missing_openpyxl(client, with_transactions, monkeypatch):
    """If openpyxl is somehow missing, the endpoint must return JSON 500."""
    import builtins
    real_import = builtins.__import__

    def guarded(name, *a, **kw):
        if name == "openpyxl" or name.startswith("openpyxl."):
            raise ImportError("simulated openpyxl missing")
        return real_import(name, *a, **kw)

    monkeypatch.setattr(builtins, "__import__", guarded)
    r = client.get("/api/transactions/export?format=xlsx")
    assert r.status_code == 500
    assert "error" in r.get_json()


def test_export_filename_includes_range(client, with_transactions):
    """The filename should embed the covered date range."""
    r = client.get("/api/transactions/export?format=csv")
    cd = r.headers["Content-Disposition"]
    assert "_20251213_to_20251215.csv" in cd
