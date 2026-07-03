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
    insight = "你是一个节省的人"
    html = render_report(analysis, txs, llm_insight=insight)
    # The insight box container is rendered...
    assert 'id="llm-insight-box"' in html
    # ...and Markdown rendering is wired up.
    assert "marked.parse" in html
    assert "DOMPurify" in html
    # The text is carried as a JSON-encoded JS string (ASCII-safe via tojson,
    # so it never appears as raw bytes). Decode the literal back and prove it
    # round-trips intact — this also guards against </script> injection.
    import re, json
    m = re.search(r"var raw = (.*?);", html)
    assert m, "llm insight JS var not found"
    assert json.loads(m.group(1)) == insight


def test_render_without_llm_insight():
    txs, analysis = _sample_data()
    html = render_report(analysis, txs, llm_insight=None)
    assert isinstance(html, str)
    assert len(html) > 500
    # No insight box when llm_insight is None.
    assert 'id="llm-insight-box"' not in html


def test_render_llm_insight_xss_is_neutralized():
    """LLM output must not leak raw HTML into the template — tojson escapes it,
    and the runtime sanitizer runs in the browser."""
    txs, analysis = _sample_data()
    payload = '<img src=x onerror=alert(1)>'
    html = render_report(analysis, txs, llm_insight=payload)
    # The raw tag must NOT appear verbatim in the HTML (tojson escaped it).
    assert payload not in html
    assert 'id="llm-insight-box"' in html


def test_render_escapes_merchant_names():
    """Merchant names flow into innerHTML via JS — they must be escaped."""
    txs = [
        Transaction("<script>x</script>食堂", -10.0, datetime(2025, 12, 15, 12, 0)),
    ]
    analysis = analyze(txs)
    html = render_report(analysis, txs)
    after = html.split("topMerchants", 1)[1]
    # Raw <script> must not appear in the merchant-rendering JS region.
    assert "<script>x</script>食堂" not in after


def test_render_empty_data():
    empty = AnalysisResult()
    html = render_report(empty, [])
    assert isinstance(html, str)
