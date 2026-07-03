"""Tests for llm.insights helpers."""
import pytest
from unittest.mock import MagicMock, patch

from llm.insights import _build_prompt, generate_insight, test_connection as llm_test_connection
from analyzer.stats import AnalysisResult
from config import AppConfig


def _make_analysis():
    a = AnalysisResult()
    a.total_count = 10
    a.total_expense = 100.0
    a.expense_count = 8
    a.total_recharge = 200.0
    a.daily_avg_expense = 12.5
    a.monthly = [{"month": "2025-09", "expense": -50.0, "recharge": 100.0, "count": 5}]
    a.categories = [{"category": "餐饮", "total": 60.0, "count": 5, "avg": 12.0, "percentage": 60.0}]
    a.top_merchants = [{"merchant": "食堂", "total": 50.0, "count": 4}]
    a.meal_times = [{"period": "午餐 (10-14)", "amount": 30.0, "percentage": 50.0}]
    from datetime import datetime
    a.date_range = (datetime(2025, 9, 1), datetime(2025, 9, 30))
    return a


def test_build_prompt_includes_all_sections():
    analysis = _make_analysis()
    prompt = _build_prompt(analysis)
    assert "总消费" in prompt
    assert "总充值" in prompt
    assert "2025-09" in prompt
    assert "餐饮" in prompt
    assert "食堂" in prompt
    assert "午餐" in prompt


def test_generate_insight_skips_when_not_ready():
    cfg = AppConfig()
    result = generate_insight(_make_analysis(), cfg)
    assert result is None


def test_generate_insight_returns_text_on_success():
    cfg = AppConfig()
    cfg.llm.api_key = "sk-test"
    cfg.llm.base_url = "https://api.test/v1"
    cfg.llm.model = "test-model"
    cfg.llm.enabled = True

    fake_response = MagicMock()
    fake_response.choices = [MagicMock()]
    fake_response.choices[0].message.content = "  你是干饭王！  "

    fake_client = MagicMock()
    fake_client.chat.completions.create.return_value = fake_response

    with patch("llm.insights.OpenAI", return_value=fake_client):
        result = generate_insight(_make_analysis(), cfg)

    assert result == "你是干饭王！"  # trimmed


def test_generate_insight_returns_none_on_error():
    cfg = AppConfig()
    cfg.llm.api_key = "sk-test"
    cfg.llm.base_url = "https://api.test/v1"
    cfg.llm.enabled = True

    with patch("llm.insights.OpenAI", side_effect=Exception("boom")):
        result = generate_insight(_make_analysis(), cfg)

    assert result is None


def test_test_connection_rejects_empty_config():
    ok, msg = llm_test_connection(AppConfig())
    assert ok is False
    assert "为空" in msg


def test_test_connection_success():
    cfg = AppConfig()
    cfg.llm.api_key = "sk-test"
    cfg.llm.base_url = "https://api.test/v1"
    cfg.llm.model = "test-model"

    fake_response = MagicMock()
    fake_response.choices = [MagicMock()]
    fake_response.choices[0].message.content = "pong"
    fake_response.model = "test-model"

    fake_client = MagicMock()
    fake_client.chat.completions.create.return_value = fake_response

    with patch("llm.insights.OpenAI", return_value=fake_client):
        ok, msg = llm_test_connection(cfg)

    assert ok is True
    assert "test-model" in msg


def test_test_connection_reports_error():
    cfg = AppConfig()
    cfg.llm.api_key = "sk-test"
    cfg.llm.base_url = "https://api.test/v1"

    with patch("llm.insights.OpenAI", side_effect=Exception("network down")):
        ok, msg = llm_test_connection(cfg)

    assert ok is False
    assert "network down" in msg