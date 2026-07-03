"""LLM-powered consumer insight generation.

Uses any OpenAI-compatible chat completion endpoint (DeepSeek, Qwen,
SiliconFlow, Zhipu, OpenAI, etc). The endpoint and credentials are
configured at runtime via the web UI and stored in a local config file.
"""
from __future__ import annotations

import logging
from typing import Tuple

from openai import OpenAI

from analyzer.stats import AnalysisResult
from config import AppConfig

logger = logging.getLogger(__name__)


SYSTEM_PROMPT = """你是一个校园卡消费分析助手。根据用户提供的消费统计数据，用轻松有趣的语气生成个性化消费洞察。
要求：
- 300字以内
- 指出消费特点和趋势
- 给出1-2条实用建议
- 可以适当用emoji
- 使用中文"""


def _build_prompt(analysis: AnalysisResult) -> str:
    parts = [f"消费数据概览（共{analysis.total_count}笔交易）："]
    parts.append(f"- 总消费：¥{analysis.total_expense}，{analysis.expense_count}笔")
    parts.append(f"- 总充值：¥{analysis.total_recharge}")
    parts.append(f"- 日均消费：¥{analysis.daily_avg_expense}")

    if analysis.date_range:
        parts.append(
            f"- 时间跨度：{analysis.date_range[0].strftime('%Y-%m-%d')} ~ "
            f"{analysis.date_range[1].strftime('%Y-%m-%d')}"
        )

    if analysis.monthly:
        parts.append("\n月度消费：")
        for m in analysis.monthly:
            parts.append(
                f"  {m['month']}：消费¥{abs(m['expense']):.0f}，充值¥{m['recharge']:.0f}"
            )

    if analysis.categories:
        parts.append("\n消费分类（按金额排序）：")
        for c in analysis.categories[:5]:
            parts.append(
                f"  {c['category']}：¥{c['total']}（{c['count']}笔，占{c['percentage']}%）"
            )

    if analysis.top_merchants:
        parts.append("\n消费最多的商户：")
        for m in analysis.top_merchants[:5]:
            parts.append(f"  {m['merchant']}：¥{m['total']}（{m['count']}次）")

    if analysis.meal_times:
        parts.append("\n用餐时段分布：")
        for m in analysis.meal_times:
            parts.append(f"  {m['period']}：{m['percentage']}%")

    return "\n".join(parts)


def generate_insight(analysis: AnalysisResult, config: AppConfig) -> str | None:
    """Generate personalized insight using the configured LLM.

    Args:
        analysis: Computed analysis results.
        config: App config with LLM API settings.

    Returns:
        LLM-generated insight text, or None on failure / not configured.
    """
    if not config.llm.is_ready():
        logger.info("LLM not ready, skipping insight generation")
        return None

    try:
        client = OpenAI(
            api_key=config.llm.api_key,
            base_url=config.llm.base_url,
            timeout=60.0,
        )
        prompt = _build_prompt(analysis)
        response = client.chat.completions.create(
            model=config.llm.model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": f"请分析以下校园卡消费数据并给出洞察：\n\n{prompt}",
                },
            ],
            max_tokens=800,
            temperature=0.7,
        )
        return (response.choices[0].message.content or "").strip()
    except Exception as e:
        logger.error(f"LLM insight generation failed: {e}")
        return None


def test_connection(config: AppConfig) -> Tuple[bool, str]:
    """Probe the LLM endpoint with a tiny prompt.

    Returns (ok, message). `message` is human-readable and safe to surface
    directly in the UI.
    """
    if not config.llm.api_key or not config.llm.base_url:
        return False, "API Key 或 Base URL 为空"

    try:
        client = OpenAI(
            api_key=config.llm.api_key,
            base_url=config.llm.base_url,
            timeout=20.0,
        )
        response = client.chat.completions.create(
            model=config.llm.model or "deepseek-chat",
            messages=[{"role": "user", "content": "ping"}],
            max_tokens=4,
            temperature=0,
        )
        # Touch the response to surface network/parse errors early.
        _ = response.choices[0].message.content
        return True, f"连接成功 (model={response.model})"
    except Exception as e:
        err = str(e)
        # Trim noisy stack traces but keep the first line informative.
        short = err.split("\n", 1)[0][:200]
        return False, f"连接失败: {short}"