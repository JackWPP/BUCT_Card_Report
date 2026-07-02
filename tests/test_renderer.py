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
