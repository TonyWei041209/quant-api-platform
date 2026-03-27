"""Structured output schemas for AI-powered research analysis."""
from __future__ import annotations
from typing import Optional
from pydantic import BaseModel, Field
from enum import StrEnum

class ConfidenceLevel(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INSUFFICIENT_DATA = "insufficient_data"

class ValidationVerdict(StrEnum):
    AGREE = "agree"
    AGREE_WITH_RESERVATIONS = "agree_with_reservations"
    DISAGREE = "disagree"
    INSUFFICIENT_INFORMATION = "insufficient_information"

class ThesisType(StrEnum):
    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"
    UNCLEAR = "unclear"

class Urgency(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    NONE = "none"

class ResearchSummary(BaseModel):
    """Primary research output from GPT-5.4."""
    instrument: str = Field(description="Ticker or instrument name")
    thesis: str = Field(description="Core investment thesis (2-4 sentences)")
    thesis_type: ThesisType = ThesisType.UNCLEAR
    key_drivers: list[str] = Field(default_factory=list, description="Key drivers supporting thesis")
    key_risks: list[str] = Field(default_factory=list, description="Key risks that could invalidate thesis")
    regime_view: str = Field(default="", description="Current market regime assessment")
    confidence_level: ConfidenceLevel = ConfidenceLevel.INSUFFICIENT_DATA
    missing_information: list[str] = Field(default_factory=list, description="What data/info is missing to strengthen thesis")
    suggested_next_steps: list[str] = Field(default_factory=list, description="Recommended next research actions")
    thesis_invalidation_signals: list[str] = Field(default_factory=list, description="Signals that would break this thesis")
    fact_vs_inference: dict[str, str] = Field(default_factory=dict, description="Explicit fact/inference/speculation labels")

class ValidationSummary(BaseModel):
    """Second-opinion validation from Gemini 2.5 Pro."""
    agrees_with_primary: ValidationVerdict = ValidationVerdict.INSUFFICIENT_INFORMATION
    agreement_points: list[str] = Field(default_factory=list)
    disagreement_points: list[str] = Field(default_factory=list)
    overlooked_risks: list[str] = Field(default_factory=list)
    unsupported_claims: list[str] = Field(default_factory=list)
    additional_considerations: list[str] = Field(default_factory=list)
    recommendation: str = Field(default="", description="Validator's overall recommendation")
    confidence_level: ConfidenceLevel = ConfidenceLevel.INSUFFICIENT_DATA

class PreprocessSummary(BaseModel):
    """Cheap preprocessing output from Flash-Lite."""
    doc_type: str = Field(default="unknown", description="Document type classification")
    short_summary: str = Field(default="", description="1-3 sentence summary")
    extracted_entities: list[str] = Field(default_factory=list, description="Named entities extracted")
    event_tags: list[str] = Field(default_factory=list, description="Event classification tags")
    urgency: Urgency = Urgency.NONE
    follow_up_needed: bool = False
    key_numbers: dict[str, str] = Field(default_factory=dict, description="Key numerical data points")

class AICallLog(BaseModel):
    """Audit log entry for an AI call."""
    provider: str
    model: str
    lane: str  # cheap_preprocess / primary_research / validation
    mode: str = "real"  # real / mock
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    total_tokens: Optional[int] = None
    latency_ms: int = 0
    success: bool = True
    schema_valid: bool = True
    error_message: Optional[str] = None
    cost_estimate_usd: Optional[float] = None
