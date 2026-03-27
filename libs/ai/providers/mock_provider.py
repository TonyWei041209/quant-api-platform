"""Mock AI provider for development, testing, and demo without API keys."""
from __future__ import annotations
from typing import Any, Optional, Type
from pydantic import BaseModel
import json
import random
import asyncio
import structlog

from libs.ai.providers.base import BaseAIProvider

logger = structlog.get_logger(__name__)

# Pre-built fixture responses keyed by schema name
FIXTURES = {
    "ResearchSummary": [
        {
            "instrument": "{instrument}",
            "thesis": "Based on available data, {instrument} shows mixed signals. Revenue growth remains solid but margin pressure from rising costs creates uncertainty. The thesis depends heavily on whether management can execute on cost optimization while maintaining growth momentum.",
            "thesis_type": "neutral",
            "key_drivers": [
                "Revenue growth above industry average (FACT: from financial statements)",
                "Market share expansion in core segments (INFERENCE: based on revenue mix)",
                "Product pipeline indicates potential upside (SPECULATION: based on management commentary)"
            ],
            "key_risks": [
                "Margin compression from input cost inflation",
                "Competitive pressure in key markets",
                "Regulatory uncertainty in primary operating regions",
                "Valuation premium may not sustain if growth decelerates"
            ],
            "regime_view": "Current market environment favors quality over momentum. Elevated volatility suggests caution on high-beta names.",
            "confidence_level": "medium",
            "missing_information": [
                "Latest quarterly guidance details",
                "Insider transaction patterns",
                "Customer concentration data",
                "Detailed segment-level margin trends"
            ],
            "suggested_next_steps": [
                "Review latest earnings transcript for management tone",
                "Compare valuation multiples vs sector peers",
                "Run backtest on similar historical setups",
                "Check for upcoming catalyst dates"
            ],
            "thesis_invalidation_signals": [
                "Two consecutive quarters of revenue decline",
                "Gross margin falling below 35%",
                "Loss of major customer or contract",
                "Management credibility erosion (guidance misses)"
            ],
            "fact_vs_inference": {
                "revenue_growth": "FACT",
                "market_share_expansion": "INFERENCE",
                "cost_optimization_success": "SPECULATION"
            }
        },
        {
            "instrument": "{instrument}",
            "thesis": "Current evidence suggests elevated downside risk for {instrument}. Multiple headwinds are converging including margin pressure, competitive threats, and potential regulatory action. Insufficient data exists to support a constructive thesis at this time.",
            "thesis_type": "bearish",
            "key_drivers": [
                "Decelerating revenue growth trajectory (FACT: trailing 3Q trend)",
                "Management has lowered forward guidance (FACT: from earnings call)",
                "Sector rotation away from growth names (INFERENCE: based on fund flows)"
            ],
            "key_risks": [
                "Short squeeze risk if sentiment shifts suddenly",
                "Potential acquisition premium not reflected",
                "New product launch could change trajectory",
                "Bear case may already be priced in"
            ],
            "regime_view": "Defensive positioning appropriate in current macro environment. Risk-off sentiment likely to persist near-term.",
            "confidence_level": "low",
            "missing_information": [
                "Updated short interest data",
                "Institutional ownership changes",
                "Supply chain disruption impact quantification",
                "Competitive response timeline"
            ],
            "suggested_next_steps": [
                "Monitor next earnings for guidance trajectory",
                "Assess technical support levels",
                "Review credit market signals if applicable",
                "Set thesis invalidation triggers before acting"
            ],
            "thesis_invalidation_signals": [
                "Revenue reacceleration above 15% YoY",
                "Significant insider buying cluster",
                "Major partnership or contract announcement",
                "Sector-wide re-rating catalyst"
            ],
            "fact_vs_inference": {
                "revenue_deceleration": "FACT",
                "guidance_reduction": "FACT",
                "sector_rotation": "INFERENCE"
            }
        },
        {
            "instrument": "{instrument}",
            "thesis": "Insufficient data available to form a well-supported thesis for {instrument}. Key financial metrics, recent filings, and market context are needed before any directional view can be responsibly constructed.",
            "thesis_type": "unclear",
            "key_drivers": [],
            "key_risks": [
                "Acting without sufficient information",
                "Confirmation bias from limited data points",
                "Unknown unknowns in current market regime"
            ],
            "regime_view": "Unable to assess without more context.",
            "confidence_level": "insufficient_data",
            "missing_information": [
                "Recent financial statements",
                "Current valuation metrics",
                "Sector comparison data",
                "Recent news and events",
                "Technical price action context"
            ],
            "suggested_next_steps": [
                "Gather latest financial data",
                "Review recent SEC filings",
                "Check for upcoming earnings or events",
                "Establish baseline valuation framework"
            ],
            "thesis_invalidation_signals": [],
            "fact_vs_inference": {}
        }
    ],
    "ValidationSummary": [
        {
            "agrees_with_primary": "agree_with_reservations",
            "agreement_points": [
                "Core thesis direction is reasonable given available data",
                "Key risk identification is adequate"
            ],
            "disagreement_points": [
                "Confidence level may be overstated given data gaps",
                "Regime assessment lacks quantitative backing"
            ],
            "overlooked_risks": [
                "Currency exposure not addressed",
                "Concentration risk in top revenue sources",
                "Potential for multiple compression in rising rate environment"
            ],
            "unsupported_claims": [
                "Market share expansion claim lacks direct evidence",
                "Cost optimization timeline is speculative"
            ],
            "additional_considerations": [
                "Consider position sizing given uncertainty level",
                "Recommend setting hard stop-loss levels before entry",
                "Cross-check with technical analysis for timing"
            ],
            "recommendation": "The primary analysis provides a reasonable starting framework but overstates confidence. Recommend reducing position size and establishing clear invalidation triggers before acting.",
            "confidence_level": "medium"
        },
        {
            "agrees_with_primary": "disagree",
            "agreement_points": [
                "Data sources cited are valid"
            ],
            "disagreement_points": [
                "Thesis underestimates competitive threats",
                "Valuation analysis is incomplete",
                "Risk section lacks quantification"
            ],
            "overlooked_risks": [
                "Sector-wide margin compression trend",
                "Management track record of overpromising",
                "Liquidity risk in current market conditions"
            ],
            "unsupported_claims": [
                "Growth sustainability assumption lacks evidence",
                "Market position defensibility is asserted not demonstrated"
            ],
            "additional_considerations": [
                "Primary analysis shows signs of confirmation bias",
                "Consider waiting for more data before forming directional view",
                "Current loss environment warrants extra caution"
            ],
            "recommendation": "Primary analysis contains significant gaps and unsupported assumptions. Do not rely on this thesis for position decisions without substantial additional research.",
            "confidence_level": "medium"
        }
    ],
    "PreprocessSummary": [
        {
            "doc_type": "earnings_report",
            "short_summary": "Company reported Q4 results with revenue of $XX billion, beating estimates by 3%. EPS came in at $X.XX vs $X.XX expected. Management raised full-year guidance.",
            "extracted_entities": ["Company Name", "CEO Name", "Q4 2024"],
            "event_tags": ["earnings_beat", "guidance_change"],
            "urgency": "medium",
            "follow_up_needed": True,
            "key_numbers": {"revenue": "$XX.XB", "eps": "$X.XX", "guidance": "raised"}
        }
    ]
}


class MockProvider(BaseAIProvider):
    """Mock provider that returns realistic fixture data without API calls."""

    def __init__(self, latency_ms: int = 800, fail_rate: float = 0.0):
        self._latency_ms = latency_ms
        self._fail_rate = fail_rate

    @property
    def provider_name(self) -> str:
        return "mock"

    async def generate(
        self,
        prompt: str,
        *,
        model: str = "mock-model",
        system_prompt: str = "",
        temperature: float = 0.3,
        max_tokens: int = 2000,
        response_schema: Optional[Type[BaseModel]] = None,
        timeout: float = 60.0,
    ) -> dict[str, Any]:
        # Simulate latency
        await asyncio.sleep(self._latency_ms / 1000)

        # Simulate random failures
        if random.random() < self._fail_rate:
            raise Exception("Mock provider simulated failure")

        # Extract instrument from prompt if possible
        instrument = "UNKNOWN"
        for marker in ["Instrument:", "INSTRUMENT:", "instrument:"]:
            if marker in prompt:
                rest = prompt.split(marker)[1].strip()
                instrument = rest.split("\n")[0].split("(")[0].strip()[:30]
                break

        # Select fixture based on schema
        schema_name = response_schema.__name__ if response_schema else "ResearchSummary"
        fixtures = FIXTURES.get(schema_name, FIXTURES["ResearchSummary"])
        fixture = random.choice(fixtures)

        # Replace instrument placeholder
        content = json.dumps(fixture).replace("{instrument}", instrument)

        return {
            "content": content,
            "model": f"mock-{schema_name.lower()}",
            "usage": {
                "prompt_tokens": len(prompt.split()) * 2,
                "completion_tokens": len(content.split()) * 2,
                "total_tokens": (len(prompt.split()) + len(content.split())) * 2,
            },
        }
