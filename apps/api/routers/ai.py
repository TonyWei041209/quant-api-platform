"""AI Research API endpoints.

These endpoints provide AI-powered research analysis.
They do NOT make trading decisions or create orders.
All outputs are advisory research context only.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional

from libs.ai.research_service import (
    generate_research_summary,
    validate_research,
    preprocess_text,
    generate_thesis_draft,
    generate_risk_checklist,
    get_ai_call_logs,
)

router = APIRouter()


class ResearchRequest(BaseModel):
    instrument_name: str = Field(description="Company/instrument name")
    ticker: str = Field(description="Ticker symbol")
    asset_type: str = "common_stock"
    context: str = Field(default="", description="Additional research context")


class ValidationRequest(BaseModel):
    primary_analysis: str = Field(description="The primary research output to validate")
    instrument_name: str
    ticker: str
    context: str = ""


class PreprocessRequest(BaseModel):
    text: str = Field(description="Text to preprocess")


class ThesisDraftRequest(BaseModel):
    instrument_name: str
    ticker: str
    context: str = ""
    recent_notes: str = ""


class RiskChecklistRequest(BaseModel):
    instrument_name: str
    ticker: str
    thesis: str = ""
    context: str = ""


@router.post("/research-summary")
async def ai_research_summary(req: ResearchRequest):
    """Generate AI research summary using primary research lane (GPT-5.4).

    This is advisory research context only — NOT a trading recommendation.
    """
    try:
        result, meta = await generate_research_summary(
            instrument_name=req.instrument_name,
            ticker=req.ticker,
            asset_type=req.asset_type,
            context=req.context,
        )
        return {
            "result": result.model_dump() if result else None,
            "meta": {
                "lane": meta.get("lane"),
                "provider": meta.get("provider"),
                "model": meta.get("model"),
                "latency_ms": meta.get("latency_ms"),
                "schema_valid": meta.get("schema_valid", False),
                "tokens": meta.get("usage", {}).get("total_tokens"),
            },
            "disclaimer": "This is AI-generated research context, not a trading recommendation. All claims should be independently verified.",
        }
    except ValueError as e:
        raise HTTPException(status_code=503, detail=f"AI provider not configured: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI analysis failed: {e}")


@router.post("/validate")
async def ai_validate(req: ValidationRequest):
    """Validate primary research using validation lane (Gemini 2.5 Pro).

    Provides critical second-opinion analysis.
    """
    try:
        result, meta = await validate_research(
            primary_analysis=req.primary_analysis,
            instrument_name=req.instrument_name,
            ticker=req.ticker,
            context=req.context,
        )
        return {
            "result": result.model_dump() if result else None,
            "meta": {
                "lane": meta.get("lane"),
                "provider": meta.get("provider"),
                "model": meta.get("model"),
                "latency_ms": meta.get("latency_ms"),
                "schema_valid": meta.get("schema_valid", False),
                "tokens": meta.get("usage", {}).get("total_tokens"),
            },
            "disclaimer": "This is a second-opinion validation, not a trading recommendation.",
        }
    except ValueError as e:
        raise HTTPException(status_code=503, detail=f"AI provider not configured: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI validation failed: {e}")


@router.post("/preprocess")
async def ai_preprocess(req: PreprocessRequest):
    """Preprocess text using cheap preprocessing lane (Flash-Lite)."""
    try:
        result, meta = await preprocess_text(req.text)
        return {
            "result": result.model_dump() if result else None,
            "meta": {
                "lane": meta.get("lane"),
                "provider": meta.get("provider"),
                "model": meta.get("model"),
                "latency_ms": meta.get("latency_ms"),
                "tokens": meta.get("usage", {}).get("total_tokens"),
            },
        }
    except ValueError as e:
        raise HTTPException(status_code=503, detail=f"AI provider not configured: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI preprocessing failed: {e}")


@router.post("/thesis-draft")
async def ai_thesis_draft(req: ThesisDraftRequest):
    """Generate thesis draft for note-taking."""
    try:
        result, meta = await generate_thesis_draft(
            instrument_name=req.instrument_name,
            ticker=req.ticker,
            context=req.context,
            recent_notes=req.recent_notes,
        )
        return {
            "result": result.model_dump() if result else None,
            "meta": {
                "lane": meta.get("lane"),
                "provider": meta.get("provider"),
                "model": meta.get("model"),
                "latency_ms": meta.get("latency_ms"),
                "tokens": meta.get("usage", {}).get("total_tokens"),
            },
            "disclaimer": "This is an AI-generated thesis draft for research purposes only.",
        }
    except ValueError as e:
        raise HTTPException(status_code=503, detail=f"AI provider not configured: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI thesis draft failed: {e}")


@router.post("/risk-checklist")
async def ai_risk_checklist(req: RiskChecklistRequest):
    """Generate risk checklist for a position/candidate."""
    try:
        result, meta = await generate_risk_checklist(
            instrument_name=req.instrument_name,
            ticker=req.ticker,
            thesis=req.thesis,
            context=req.context,
        )
        return {
            "result": result,
            "meta": {
                "lane": meta.get("lane"),
                "provider": meta.get("provider"),
                "model": meta.get("model"),
                "latency_ms": meta.get("latency_ms"),
                "tokens": meta.get("usage", {}).get("total_tokens"),
            },
            "disclaimer": "This is an AI-generated risk assessment for research purposes only.",
        }
    except ValueError as e:
        raise HTTPException(status_code=503, detail=f"AI provider not configured: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI risk checklist failed: {e}")


@router.get("/logs")
async def ai_logs(limit: int = 20):
    """Get recent AI call audit logs."""
    logs = get_ai_call_logs(limit)
    return {
        "total": len(logs),
        "items": [log.model_dump() for log in logs],
    }


@router.post("/evaluate")
async def ai_evaluate():
    """Run AI evaluation harness against current provider configuration.

    Tests output quality, schema compliance, and financial guardrails.
    Works in both real and mock mode.
    """
    try:
        from libs.ai.evaluation import run_evaluation
        report = await run_evaluation()
        return report
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Evaluation failed: {e}")


@router.get("/status")
async def ai_status():
    """Get current AI provider status and configuration."""
    import os
    from libs.ai.router import LANE_CONFIG, _get_provider

    lanes = {}
    for lane_name, config in LANE_CONFIG.items():
        provider = _get_provider(config["provider"])
        lanes[lane_name] = {
            "provider": config["provider"],
            "model": config["model"],
            "mode": "mock" if provider.provider_name == "mock" else "real",
            "description": config["description"],
        }

    return {
        "openai_configured": bool(os.getenv("OPENAI_API_KEY")),
        "gemini_configured": bool(os.getenv("GEMINI_API_KEY")),
        "lanes": lanes,
        "guardrails": {
            "no_direct_orders": True,
            "approval_gate_mandatory": True,
            "live_submit_disabled": True,
            "structured_output_required": True,
            "financial_guardrails_active": True,
        },
    }
