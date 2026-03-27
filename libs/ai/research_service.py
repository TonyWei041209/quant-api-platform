"""High-level AI research service for the platform.

This service connects the AI router to platform-specific research workflows.
It does NOT make trading decisions or create orders.
"""
from __future__ import annotations
from typing import Optional
import structlog

from libs.ai.router import route_call, get_recent_logs
from libs.ai.schemas import ResearchSummary, ValidationSummary, PreprocessSummary, AICallLog
from libs.ai import prompts

logger = structlog.get_logger(__name__)


async def generate_research_summary(
    instrument_name: str,
    ticker: str,
    asset_type: str = "common_stock",
    context: str = "",
) -> tuple[Optional[ResearchSummary], dict]:
    """Generate a structured research summary using the primary research lane."""
    prompt = prompts.RESEARCH_SUMMARY_PROMPT.format(
        instrument_name=instrument_name,
        ticker=ticker,
        asset_type=asset_type,
        context=context or "No additional context provided. Base analysis on general market knowledge.",
    )
    return await route_call(
        "primary_research",
        prompt,
        system_prompt=prompts.FINANCIAL_SYSTEM_PROMPT,
        response_schema=ResearchSummary,
        max_tokens=3000,
    )


async def validate_research(
    primary_analysis: str,
    instrument_name: str,
    ticker: str,
    context: str = "",
) -> tuple[Optional[ValidationSummary], dict]:
    """Validate a primary research output using the validation lane."""
    prompt = prompts.VALIDATION_PROMPT.format(
        primary_analysis=primary_analysis,
        instrument_name=instrument_name,
        ticker=ticker,
        context=context or "No additional context.",
    )
    return await route_call(
        "validation",
        prompt,
        system_prompt=prompts.FINANCIAL_SYSTEM_PROMPT,
        response_schema=ValidationSummary,
        max_tokens=2000,
    )


async def preprocess_text(text: str) -> tuple[Optional[PreprocessSummary], dict]:
    """Preprocess text using the cheap preprocessing lane."""
    prompt = prompts.PREPROCESS_PROMPT.format(text=text[:8000])  # Limit input size
    return await route_call(
        "cheap_preprocess",
        prompt,
        response_schema=PreprocessSummary,
        max_tokens=1000,
    )


async def generate_thesis_draft(
    instrument_name: str,
    ticker: str,
    context: str = "",
    recent_notes: str = "",
) -> tuple[Optional[ResearchSummary], dict]:
    """Generate a thesis draft for note-taking."""
    prompt = prompts.THESIS_DRAFT_PROMPT.format(
        instrument_name=instrument_name,
        ticker=ticker,
        context=context or "No specific context.",
        recent_notes=recent_notes or "No recent notes.",
    )
    return await route_call(
        "primary_research",
        prompt,
        system_prompt=prompts.FINANCIAL_SYSTEM_PROMPT,
        response_schema=ResearchSummary,
        max_tokens=2500,
    )


async def generate_risk_checklist(
    instrument_name: str,
    ticker: str,
    thesis: str = "",
    context: str = "",
) -> tuple[Optional[dict], dict]:
    """Generate a risk checklist (returns raw dict, not strict schema)."""
    prompt = prompts.RISK_CHECKLIST_PROMPT.format(
        instrument_name=instrument_name,
        ticker=ticker,
        thesis=thesis or "No specific thesis provided.",
        context=context or "No additional context.",
    )
    result, meta = await route_call(
        "primary_research",
        prompt,
        system_prompt=prompts.FINANCIAL_SYSTEM_PROMPT,
        max_tokens=2000,
    )
    # For risk checklist, parse raw content as dict
    import json
    raw = meta.get("raw_content", "")
    try:
        if "```json" in raw:
            raw = raw.split("```json")[1].split("```")[0].strip()
        elif "```" in raw:
            raw = raw.split("```")[1].split("```")[0].strip()
        parsed = json.loads(raw)
        return parsed, meta
    except Exception:
        return {"raw_text": raw}, meta


def get_ai_call_logs(limit: int = 20) -> list[AICallLog]:
    """Get recent AI call audit logs."""
    return get_recent_logs(limit)
