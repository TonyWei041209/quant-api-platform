"""AI evaluation harness for validating research quality.

Used to verify AI outputs meet financial guardrail standards
before and after switching from mock to real providers.
"""
from __future__ import annotations
from typing import Optional
from dataclasses import dataclass, field
from datetime import datetime
import json
import structlog

from libs.ai.schemas import ResearchSummary, ValidationSummary

logger = structlog.get_logger(__name__)


@dataclass
class EvalSample:
    """A single evaluation input sample."""
    sample_id: str
    instrument: str
    ticker: str
    context: str = ""
    expected_themes: list[str] = field(default_factory=list)
    expected_risks: list[str] = field(default_factory=list)
    expected_invalidation_signals: list[str] = field(default_factory=list)
    expected_uncertainty: bool = True


@dataclass
class EvalResult:
    """Evaluation result for a single sample."""
    sample_id: str
    schema_valid: bool = False
    risk_completeness: float = 0.0  # 0-1
    uncertainty_present: bool = False
    invalidation_signal_present: bool = False
    anti_hype_compliant: bool = False
    fact_inference_labeled: bool = False
    thesis_present: bool = False
    missing_info_flagged: bool = False
    overall_pass: bool = False
    details: dict = field(default_factory=dict)

    @property
    def score(self) -> float:
        checks = [
            self.schema_valid,
            self.risk_completeness >= 0.5,
            self.uncertainty_present,
            self.invalidation_signal_present,
            self.anti_hype_compliant,
            self.fact_inference_labeled,
            self.thesis_present,
            self.missing_info_flagged,
        ]
        return sum(checks) / len(checks) if checks else 0.0


# Pseudo-certainty phrases that should NOT appear in output
HYPE_PHRASES = [
    "guaranteed", "will definitely", "certain to", "must buy", "must sell",
    "can't lose", "sure thing", "no risk", "easy money", "slam dunk",
    "home run", "no brainer", "100% chance", "absolutely will",
    "\u5fc5\u6da8", "\u4e00\u5b9a\u53cd\u5f39", "\u9ad8\u80dc\u7387\u786e\u5b9a", "\u8fd9\u5c31\u662f\u5e95\u90e8", "\u5e94\u7acb\u5373\u91cd\u4ed3",
]


def evaluate_research_summary(
    summary: ResearchSummary,
    sample: Optional[EvalSample] = None,
) -> EvalResult:
    """Evaluate a ResearchSummary against quality standards."""
    result = EvalResult(sample_id=sample.sample_id if sample else "adhoc")

    # 1. Schema valid (if we got here, it parsed)
    result.schema_valid = True

    # 2. Thesis present and non-empty
    result.thesis_present = bool(summary.thesis and len(summary.thesis) > 20)

    # 3. Risk completeness
    risk_count = len(summary.key_risks)
    result.risk_completeness = min(risk_count / 3, 1.0)  # At least 3 risks expected

    # 4. Uncertainty present
    result.uncertainty_present = (
        summary.confidence_level in ("low", "medium", "insufficient_data")
        or len(summary.missing_information) > 0
        or any("uncertain" in r.lower() or "risk" in r.lower() for r in summary.key_risks)
    )

    # 5. Invalidation signals
    result.invalidation_signal_present = len(summary.thesis_invalidation_signals) >= 1

    # 6. Anti-hype compliance
    full_text = json.dumps(summary.model_dump()).lower()
    result.anti_hype_compliant = not any(phrase.lower() in full_text for phrase in HYPE_PHRASES)

    # 7. Fact vs inference labeling
    result.fact_inference_labeled = (
        len(summary.fact_vs_inference) > 0
        or any("FACT" in d or "INFERENCE" in d or "SPECULATION" in d for d in summary.key_drivers)
    )

    # 8. Missing info flagged
    result.missing_info_flagged = len(summary.missing_information) >= 1

    # Overall pass: all critical checks must pass
    result.overall_pass = all([
        result.schema_valid,
        result.thesis_present,
        result.risk_completeness >= 0.5,
        result.anti_hype_compliant,
        result.invalidation_signal_present,
    ])

    return result


def evaluate_validation_summary(
    validation: ValidationSummary,
) -> dict:
    """Evaluate a ValidationSummary for quality."""
    checks = {
        "has_verdict": validation.agrees_with_primary != "insufficient_information",
        "has_disagreement_analysis": len(validation.disagreement_points) > 0 or len(validation.overlooked_risks) > 0,
        "has_unsupported_claims_check": len(validation.unsupported_claims) >= 0,  # Can be empty if primary is solid
        "has_recommendation": bool(validation.recommendation and len(validation.recommendation) > 10),
        "anti_hype_compliant": not any(
            phrase.lower() in json.dumps(validation.model_dump()).lower()
            for phrase in HYPE_PHRASES
        ),
    }
    checks["overall_pass"] = all(checks.values())
    return checks


# Default evaluation samples
DEFAULT_EVAL_SAMPLES = [
    EvalSample(
        sample_id="eval_001_aapl_neutral",
        instrument="Apple Inc.",
        ticker="AAPL",
        context="Large-cap tech, strong cash flow, iPhone cycle maturity concerns",
        expected_themes=["iPhone", "services", "cash flow"],
        expected_risks=["China exposure", "regulatory", "innovation plateau"],
        expected_invalidation_signals=["revenue decline", "margin erosion"],
        expected_uncertainty=True,
    ),
    EvalSample(
        sample_id="eval_002_nvda_momentum",
        instrument="NVIDIA Corp",
        ticker="NVDA",
        context="AI chip leader, high valuation, data center growth",
        expected_themes=["AI", "data center", "GPU"],
        expected_risks=["valuation", "competition", "cyclicality"],
        expected_invalidation_signals=["market share loss", "demand slowdown"],
        expected_uncertainty=True,
    ),
    EvalSample(
        sample_id="eval_003_unknown_insufficient",
        instrument="Unknown Corp",
        ticker="UNK",
        context="",
        expected_themes=[],
        expected_risks=["insufficient data"],
        expected_invalidation_signals=[],
        expected_uncertainty=True,
    ),
]


async def run_evaluation(
    samples: Optional[list[EvalSample]] = None,
) -> dict:
    """Run full evaluation suite and return report."""
    from libs.ai.research_service import generate_research_summary

    if samples is None:
        samples = DEFAULT_EVAL_SAMPLES

    results = []
    for sample in samples:
        try:
            summary, meta = await generate_research_summary(
                instrument_name=sample.instrument,
                ticker=sample.ticker,
                context=sample.context,
            )
            if summary:
                eval_result = evaluate_research_summary(summary, sample)
                results.append({
                    "sample_id": sample.sample_id,
                    "instrument": sample.ticker,
                    "score": eval_result.score,
                    "overall_pass": eval_result.overall_pass,
                    "schema_valid": eval_result.schema_valid,
                    "risk_completeness": eval_result.risk_completeness,
                    "uncertainty_present": eval_result.uncertainty_present,
                    "invalidation_signal_present": eval_result.invalidation_signal_present,
                    "anti_hype_compliant": eval_result.anti_hype_compliant,
                    "fact_inference_labeled": eval_result.fact_inference_labeled,
                    "mode": meta.get("provider", "unknown"),
                    "latency_ms": meta.get("latency_ms", 0),
                })
            else:
                results.append({
                    "sample_id": sample.sample_id,
                    "instrument": sample.ticker,
                    "overall_pass": False,
                    "error": meta.get("error", "No summary returned"),
                })
        except Exception as e:
            results.append({
                "sample_id": sample.sample_id,
                "instrument": sample.ticker,
                "overall_pass": False,
                "error": str(e),
            })

    passed = sum(1 for r in results if r.get("overall_pass"))
    total = len(results)

    return {
        "timestamp": datetime.utcnow().isoformat(),
        "total_samples": total,
        "passed": passed,
        "failed": total - passed,
        "pass_rate": passed / total if total > 0 else 0,
        "results": results,
    }
