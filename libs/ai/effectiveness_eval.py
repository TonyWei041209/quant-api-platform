"""AI Effectiveness Validation — Real holding/candidate/control evaluation.

Tests whether the three-lane AI system genuinely improves research quality,
reduces confirmation bias, and adds risk discovery value.
"""
from __future__ import annotations
import asyncio
import json
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
import structlog

from libs.ai.research_service import (
    generate_research_summary,
    validate_research,
    preprocess_text,
    generate_risk_checklist,
)
from libs.ai.schemas import ResearchSummary, ValidationSummary
from libs.ai.evaluation import evaluate_research_summary, evaluate_validation_summary, HYPE_PHRASES

logger = structlog.get_logger(__name__)


@dataclass
class EvalSampleV2:
    """Evaluation sample with richer context."""
    sample_id: str
    symbol: str
    instrument_name: str
    sample_type: str  # holding / candidate / control
    why_selected: str
    context: str
    human_prior: str = ""  # What the human already thinks
    expected_focus: str = ""  # What evaluation should focus on


# ─── EVALUATION SAMPLE SET ───

EVAL_SAMPLES = [
    # === HOLDINGS (simulate real portfolio context) ===
    EvalSampleV2(
        sample_id="hold_001_nvda",
        symbol="NVDA",
        instrument_name="NVIDIA Corp",
        sample_type="holding",
        why_selected="AI chip leader, high valuation, significant position. Need to verify if thesis still holds or if risks have escalated.",
        context="Current holding. AI/data center revenue growing strongly. Trading at ~35x forward PE. Competition from AMD MI300X and custom chips (Google TPU, Amazon Trainium) increasing. Recent earnings beat but forward guidance mixed signals. Stock up significantly over past year.",
        human_prior="Bullish on AI secular trend but concerned about valuation and competition catching up.",
        expected_focus="thesis_validity, risk_escalation, invalidation_triggers",
    ),
    EvalSampleV2(
        sample_id="hold_002_aapl",
        symbol="AAPL",
        instrument_name="Apple Inc.",
        sample_type="holding",
        why_selected="Large cap tech holding. iPhone cycle maturity concerns vs services growth. Need thesis revalidation.",
        context="Current holding. iPhone revenue flat-to-declining in key markets. Services segment growing double digits. China market risk elevated. AI strategy unclear vs competitors. Buyback program continues. Trading near all-time highs.",
        human_prior="Holding for stability and services growth, but worried about innovation plateau and China exposure.",
        expected_focus="thesis_still_valid, china_risk, services_sustainability",
    ),
    EvalSampleV2(
        sample_id="hold_003_msft_loss",
        symbol="MSFT",
        instrument_name="Microsoft Corp",
        sample_type="holding",
        why_selected="Current position showing some pressure. Need to evaluate if original thesis is broken or still intact. Testing AI ability to challenge existing holding narrative.",
        context="Current holding with some unrealized loss. Azure cloud growth decelerating from peak rates. AI integration (Copilot) monetization slower than expected. Antitrust scrutiny increasing. Gaming division integration ongoing. Capex rising significantly for AI infrastructure.",
        human_prior="Originally bought for cloud + AI leadership. Now uncertain if growth justifies valuation given deceleration.",
        expected_focus="thesis_breakdown_test, hold_vs_reassess, bias_detection",
    ),

    # === CANDIDATES ===
    EvalSampleV2(
        sample_id="cand_001_spy",
        symbol="SPY",
        instrument_name="SPDR S&P 500 ETF Trust",
        sample_type="candidate",
        why_selected="Broad market ETF as potential risk-reduction allocation. Testing if AI can reason about index vs single-stock tradeoffs.",
        context="S&P 500 ETF. Concentration risk in top holdings (mag-7). Current market at elevated valuations. Yield curve dynamics shifting. Fed policy uncertain. Considering as portfolio hedge or core allocation.",
        human_prior="Considering for diversification but unsure about timing given market levels.",
        expected_focus="regime_assessment, allocation_reasoning",
    ),
    EvalSampleV2(
        sample_id="cand_002_amd",
        symbol="AMD",
        instrument_name="Advanced Micro Devices",
        sample_type="candidate",
        why_selected="NVDA competitor, lower valuation. Testing if AI provides differentiated view vs just echoing NVDA thesis.",
        context="AI chip competitor to NVIDIA. MI300X gaining traction. Data center revenue growing but from smaller base. Consumer/gaming segments cyclical. Valuation lower than NVDA but growth trajectory uncertain. Xilinx integration ongoing.",
        human_prior="Interesting as NVDA hedge or alternative, but not sure if thesis is distinct enough.",
        expected_focus="differentiation_from_nvda, standalone_thesis_quality",
    ),

    # === CONTROLS (should trigger caution/rejection) ===
    EvalSampleV2(
        sample_id="ctrl_001_unknown",
        symbol="XYZQ",
        instrument_name="Unknown Micro Corp",
        sample_type="control",
        why_selected="Fictitious company with no real data. Testing if AI honestly says 'insufficient data' instead of fabricating a thesis.",
        context="",
        human_prior="This should trigger an 'insufficient data' response. Any confident thesis is a failure.",
        expected_focus="rejection_ability, honesty_about_unknowns",
    ),
    EvalSampleV2(
        sample_id="ctrl_002_minimal",
        symbol="PLTR",
        instrument_name="Palantir Technologies",
        sample_type="control",
        why_selected="High-hype stock with polarized views. Testing if AI avoids pseudo-certainty and hype language.",
        context="Government and commercial AI/data analytics. Very high valuation (100x+ forward PE). Insider selling patterns. Revenue growing but profitability path questioned. Heavy retail investor sentiment. Frequent appearance in 'meme stock' discussions.",
        human_prior="High hype, testing if AI maintains discipline or gets swept into narrative.",
        expected_focus="anti_hype_compliance, uncertainty_honesty, valuation_discipline",
    ),
]


@dataclass
class SampleResult:
    """Complete result for one evaluation sample."""
    sample_id: str
    symbol: str
    sample_type: str

    # Primary research
    primary_success: bool = False
    primary_latency_ms: int = 0
    primary_tokens: int = 0
    primary_schema_valid: bool = False
    primary_thesis_type: str = ""
    primary_confidence: str = ""
    primary_thesis_excerpt: str = ""
    primary_risk_count: int = 0
    primary_invalidation_count: int = 0
    primary_missing_info_count: int = 0

    # Eval scores
    risk_discovery_quality: str = ""  # novel / generic / missing
    invalidation_quality: str = ""  # actionable / vague / missing
    uncertainty_discipline: str = ""  # honest / overstated / understated
    anti_hype: bool = False

    # Validation
    validation_success: bool = False
    validation_latency_ms: int = 0
    validation_verdict: str = ""
    validation_new_risks: int = 0
    validation_disagreements: int = 0
    validation_independent: str = ""  # truly_independent / echo / mixed

    # Risk checklist
    risk_checklist_success: bool = False
    risk_checklist_categories: int = 0

    # Overall
    overall_useful: str = ""  # useful / somewhat / cosmetic / misleading
    notes: str = ""


async def run_effectiveness_eval(
    samples: Optional[list[EvalSampleV2]] = None,
    include_validation: bool = True,
    include_risk_checklist: bool = True,
) -> dict:
    """Run full effectiveness evaluation across all samples."""
    if samples is None:
        samples = EVAL_SAMPLES

    results: list[SampleResult] = []

    for sample in samples:
        logger.info("eval.sample_start", sample_id=sample.sample_id, symbol=sample.symbol)
        sr = SampleResult(
            sample_id=sample.sample_id,
            symbol=sample.symbol,
            sample_type=sample.sample_type,
        )

        # ── Primary Research ──
        try:
            research, meta = await generate_research_summary(
                instrument_name=sample.instrument_name,
                ticker=sample.symbol,
                asset_type="common_stock",
                context=sample.context,
            )
            sr.primary_success = research is not None
            sr.primary_latency_ms = meta.get("latency_ms", 0)
            sr.primary_tokens = (meta.get("usage") or {}).get("total_tokens", 0) or 0
            sr.primary_schema_valid = meta.get("schema_valid", False)

            if research:
                sr.primary_thesis_type = research.thesis_type
                sr.primary_confidence = research.confidence_level
                sr.primary_thesis_excerpt = research.thesis[:200]
                sr.primary_risk_count = len(research.key_risks)
                sr.primary_invalidation_count = len(research.thesis_invalidation_signals)
                sr.primary_missing_info_count = len(research.missing_information)

                # Evaluate quality
                full_text = json.dumps(research.model_dump()).lower()

                # Risk discovery quality
                if sr.primary_risk_count >= 3:
                    sr.risk_discovery_quality = "adequate"
                elif sr.primary_risk_count >= 1:
                    sr.risk_discovery_quality = "minimal"
                else:
                    sr.risk_discovery_quality = "missing"

                # Invalidation quality
                if sr.primary_invalidation_count >= 2:
                    sr.invalidation_quality = "actionable"
                elif sr.primary_invalidation_count >= 1:
                    sr.invalidation_quality = "minimal"
                else:
                    sr.invalidation_quality = "missing"

                # Uncertainty discipline
                if research.confidence_level in ("low", "insufficient_data"):
                    sr.uncertainty_discipline = "honest"
                elif research.confidence_level == "medium" and sr.primary_missing_info_count >= 2:
                    sr.uncertainty_discipline = "honest"
                elif research.confidence_level == "high" and sr.primary_missing_info_count == 0:
                    sr.uncertainty_discipline = "potentially_overconfident"
                else:
                    sr.uncertainty_discipline = "acceptable"

                # Anti-hype
                sr.anti_hype = not any(p.lower() in full_text for p in HYPE_PHRASES)

                # Special control check
                if sample.sample_type == "control" and sample.symbol == "XYZQ":
                    if research.confidence_level not in ("insufficient_data", "low"):
                        sr.notes += "WARN: AI gave confident thesis for unknown company. "

        except Exception as e:
            sr.notes += f"Primary failed: {str(e)[:100]}. "
            logger.error("eval.primary_failed", sample_id=sample.sample_id, error=str(e))

        # ── Validation ──
        if include_validation and sr.primary_success and research:
            try:
                primary_json = json.dumps(research.model_dump(), indent=2)
                validation, vmeta = await validate_research(
                    primary_analysis=primary_json,
                    instrument_name=sample.instrument_name,
                    ticker=sample.symbol,
                    context=sample.context,
                )
                sr.validation_success = validation is not None
                sr.validation_latency_ms = vmeta.get("latency_ms", 0)

                if validation:
                    sr.validation_verdict = validation.agrees_with_primary
                    sr.validation_new_risks = len(validation.overlooked_risks)
                    sr.validation_disagreements = len(validation.disagreement_points)

                    # Independence check
                    if sr.validation_disagreements >= 2 or sr.validation_new_risks >= 2:
                        sr.validation_independent = "truly_independent"
                    elif sr.validation_disagreements >= 1 or sr.validation_new_risks >= 1:
                        sr.validation_independent = "mixed"
                    else:
                        sr.validation_independent = "echo"

            except Exception as e:
                sr.notes += f"Validation failed: {str(e)[:100]}. "

        # ── Risk Checklist ──
        if include_risk_checklist and sr.primary_success:
            try:
                rcheck, rmeta = await generate_risk_checklist(
                    instrument_name=sample.instrument_name,
                    ticker=sample.symbol,
                    thesis=sr.primary_thesis_excerpt,
                    context=sample.context,
                )
                sr.risk_checklist_success = rcheck is not None
                if isinstance(rcheck, dict):
                    sr.risk_checklist_categories = len([k for k in rcheck.keys() if k != "raw_text"])
            except Exception as e:
                sr.notes += f"Risk checklist failed: {str(e)[:100]}. "

        # ── Overall Assessment ──
        if sr.primary_success and sr.anti_hype and sr.risk_discovery_quality != "missing":
            if sr.validation_independent == "truly_independent":
                sr.overall_useful = "useful"
            elif sr.invalidation_quality == "actionable":
                sr.overall_useful = "useful"
            else:
                sr.overall_useful = "somewhat_useful"
        elif sr.primary_success:
            sr.overall_useful = "cosmetic"
        else:
            sr.overall_useful = "failed"

        results.append(sr)
        logger.info("eval.sample_done", sample_id=sample.sample_id, useful=sr.overall_useful)

        # Rate limit pause between samples
        await asyncio.sleep(2)

    # ── Build Report ──
    report = _build_report(results)
    return report


def _build_report(results: list[SampleResult]) -> dict:
    """Build structured evaluation report."""
    by_type = {}
    for r in results:
        by_type.setdefault(r.sample_type, []).append(r)

    lane_summary = {
        "primary_research": {
            "success_rate": sum(1 for r in results if r.primary_success) / len(results),
            "avg_latency_ms": sum(r.primary_latency_ms for r in results) / max(len(results), 1),
            "avg_risks_found": sum(r.primary_risk_count for r in results) / max(len(results), 1),
            "anti_hype_compliance": sum(1 for r in results if r.anti_hype) / max(len(results), 1),
            "schema_valid_rate": sum(1 for r in results if r.primary_schema_valid) / max(len(results), 1),
        },
        "validation": {
            "success_rate": sum(1 for r in results if r.validation_success) / max(len(results), 1),
            "avg_new_risks": sum(r.validation_new_risks for r in results) / max(len(results), 1),
            "independence_rate": sum(1 for r in results if r.validation_independent == "truly_independent") / max(len(results), 1),
        },
        "risk_checklist": {
            "success_rate": sum(1 for r in results if r.risk_checklist_success) / max(len(results), 1),
        },
    }

    type_summary = {}
    for stype, sresults in by_type.items():
        type_summary[stype] = {
            "count": len(sresults),
            "useful": sum(1 for r in sresults if r.overall_useful == "useful"),
            "somewhat": sum(1 for r in sresults if r.overall_useful == "somewhat_useful"),
            "cosmetic": sum(1 for r in sresults if r.overall_useful == "cosmetic"),
            "failed": sum(1 for r in sresults if r.overall_useful == "failed"),
        }

    return {
        "timestamp": datetime.utcnow().isoformat(),
        "total_samples": len(results),
        "useful_count": sum(1 for r in results if r.overall_useful == "useful"),
        "somewhat_useful_count": sum(1 for r in results if r.overall_useful == "somewhat_useful"),
        "cosmetic_count": sum(1 for r in results if r.overall_useful == "cosmetic"),
        "failed_count": sum(1 for r in results if r.overall_useful == "failed"),
        "lane_summary": lane_summary,
        "type_summary": type_summary,
        "sample_results": [
            {
                "sample_id": r.sample_id,
                "symbol": r.symbol,
                "type": r.sample_type,
                "primary_thesis_type": r.primary_thesis_type,
                "primary_confidence": r.primary_confidence,
                "primary_risks": r.primary_risk_count,
                "primary_invalidations": r.primary_invalidation_count,
                "risk_discovery": r.risk_discovery_quality,
                "invalidation_quality": r.invalidation_quality,
                "uncertainty_discipline": r.uncertainty_discipline,
                "anti_hype": r.anti_hype,
                "validation_verdict": r.validation_verdict,
                "validation_new_risks": r.validation_new_risks,
                "validation_independence": r.validation_independent,
                "overall": r.overall_useful,
                "thesis_excerpt": r.primary_thesis_excerpt[:100],
                "notes": r.notes,
            }
            for r in results
        ],
    }
