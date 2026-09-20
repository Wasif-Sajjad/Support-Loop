"""Tests for Epic G2 (Cost calculation & provider breakdown) and ARQ Task Queue.
"""
import pytest
from app.llm.pricing import calculate_cost, PRICING_TABLE, COST_DISCLAIMER
from app.worker import WorkerSettings, get_redis_settings, process_ticket_job


def test_pricing_calculation_groq():
    """Verify Groq Llama 3.3 70B cost calculation against published rates."""
    # 1,000 in, 1,000 out: (1 * 0.00059) + (1 * 0.00079) = 0.00138
    cost = calculate_cost("groq", 1000, 1000)
    assert cost == 0.00138

    # 500 in, 200 out: (0.5 * 0.00059) + (0.2 * 0.00079) = 0.000295 + 0.000158 = 0.000453
    cost_sub = calculate_cost("openai/gpt-oss-120b", 500, 200)
    assert cost_sub == 0.000453


def test_pricing_calculation_gemini():
    """Verify Gemini 1.5 Flash cost calculation against published rates."""
    # 1,000 in, 1,000 out: (1 * 0.000075) + (1 * 0.00030) = 0.000375
    cost = calculate_cost("gemini", 1000, 1000)
    assert cost == 0.000375

    cost_flash = calculate_cost("gemini-1.5-flash", 2000, 500)
    # (2 * 0.000075) + (0.5 * 0.00030) = 0.000150 + 0.000150 = 0.000300
    assert cost_flash == 0.0003


def test_pricing_disclaimer_label():
    """Pricing label must explicitly indicate estimated standard pricing."""
    assert "estimated at standard pricing" in COST_DISCLAIMER


def test_worker_settings_configured():
    """WorkerSettings should register process_ticket_job and valid redis settings."""
    assert process_ticket_job in WorkerSettings.functions
    redis_settings = get_redis_settings()
    assert redis_settings is not None
    assert WorkerSettings.max_jobs >= 1
