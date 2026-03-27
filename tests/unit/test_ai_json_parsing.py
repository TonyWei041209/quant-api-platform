"""Tests for AI JSON parsing robustness — covers real Gemini failure modes."""
import pytest
from libs.ai.providers.base import _extract_json_from_text, _light_json_repair, _normalize_schema_data
from libs.ai.schemas import ValidationSummary, ResearchSummary, ConfidenceLevel, ValidationVerdict


# ─── _extract_json_from_text ───

class TestExtractJson:
    def test_pure_json(self):
        """Standard JSON parses directly."""
        raw = '{"agrees_with_primary": "agree", "confidence_level": "high"}'
        result = _extract_json_from_text(raw)
        assert '"agrees_with_primary"' in result

    def test_json_code_fence(self):
        """```json ... ``` fences are stripped."""
        raw = '```json\n{"agrees_with_primary": "agree"}\n```'
        result = _extract_json_from_text(raw)
        assert '"agrees_with_primary"' in result

    def test_json_code_fence_uppercase(self):
        """```JSON ... ``` fences are stripped (case-insensitive)."""
        raw = '```JSON\n{"agrees_with_primary": "agree"}\n```'
        result = _extract_json_from_text(raw)
        assert '"agrees_with_primary"' in result

    def test_json_plain_fence(self):
        """``` ... ``` without language tag also works."""
        raw = '```\n{"agrees_with_primary": "disagree"}\n```'
        result = _extract_json_from_text(raw)
        assert '"disagree"' in result

    def test_json_with_surrounding_text(self):
        """JSON embedded in natural language explanation."""
        raw = """Here is my validation analysis:

{"agrees_with_primary": "agree_with_reservations", "disagreement_points": ["Risk underestimated"], "confidence_level": "medium"}

I hope this helps with your research."""
        result = _extract_json_from_text(raw)
        import json
        data = json.loads(result)
        assert data["agrees_with_primary"] == "agree_with_reservations"

    def test_json_with_trailing_comma(self):
        """Trailing commas are repaired."""
        raw = '{"agrees_with_primary": "agree", "disagreement_points": [],}'
        result = _extract_json_from_text(raw)
        import json
        data = json.loads(result)
        assert data["agrees_with_primary"] == "agree"

    def test_json_with_comments(self):
        """Single-line comments are removed."""
        raw = '{"agrees_with_primary": "agree", // this is the verdict\n"confidence_level": "high"}'
        result = _extract_json_from_text(raw)
        import json
        data = json.loads(result)
        assert data["confidence_level"] == "high"

    def test_empty_text_raises(self):
        """Empty text raises ValueError."""
        with pytest.raises(ValueError, match="Empty text"):
            _extract_json_from_text("")

    def test_no_json_raises(self):
        """Text with no JSON raises ValueError."""
        with pytest.raises(ValueError, match="No valid JSON"):
            _extract_json_from_text("This is just plain text with no JSON at all.")

    def test_nested_json(self):
        """Nested objects are handled correctly."""
        raw = '{"agrees_with_primary": "agree", "fact_vs_inference": {"point_a": "fact", "point_b": "inference"}}'
        result = _extract_json_from_text(raw)
        import json
        data = json.loads(result)
        assert data["fact_vs_inference"]["point_a"] == "fact"


# ─── _normalize_schema_data ───

class TestNormalizeSchemaData:
    def test_enum_case_normalization(self):
        """Enum values with wrong case are normalized."""
        data = {"agrees_with_primary": "AGREE", "confidence_level": "HIGH"}
        result = _normalize_schema_data(data, ValidationSummary)
        assert result["agrees_with_primary"] == "agree"
        assert result["confidence_level"] == "high"

    def test_mixed_case_enum(self):
        """Mixed case enum values normalize."""
        data = {"agrees_with_primary": "Agree_With_Reservations", "confidence_level": "Medium"}
        result = _normalize_schema_data(data, ValidationSummary)
        assert result["agrees_with_primary"] == "agree_with_reservations"
        assert result["confidence_level"] == "medium"

    def test_none_list_becomes_empty(self):
        """None values for list fields become []."""
        data = {"agrees_with_primary": "agree", "disagreement_points": None, "overlooked_risks": None}
        result = _normalize_schema_data(data, ValidationSummary)
        assert result["disagreement_points"] == []
        assert result["overlooked_risks"] == []

    def test_none_string_becomes_empty(self):
        """None values for string fields become ''."""
        data = {"agrees_with_primary": "agree", "recommendation": None}
        result = _normalize_schema_data(data, ValidationSummary)
        assert result["recommendation"] == ""

    def test_unknown_keys_pass_through(self):
        """Extra keys from model output pass through (Pydantic handles them)."""
        data = {"agrees_with_primary": "agree", "extra_field": "value"}
        result = _normalize_schema_data(data, ValidationSummary)
        assert result["agrees_with_primary"] == "agree"
        assert result["extra_field"] == "value"

    def test_thesis_type_normalization(self):
        """ThesisType enum normalizes correctly."""
        data = {"instrument": "NVDA", "thesis": "test", "thesis_type": "BULLISH", "confidence_level": "HIGH"}
        result = _normalize_schema_data(data, ResearchSummary)
        assert result["thesis_type"] == "bullish"
        assert result["confidence_level"] == "high"


# ─── Degraded fallback behavior ───

class TestDegradedFallback:
    def test_degraded_fallback_validation(self):
        """Degraded fallback for ValidationSummary has safe defaults."""
        from libs.ai.providers.base import BaseAIProvider
        parsed, meta = BaseAIProvider._make_degraded_fallback(
            ValidationSummary, {}, "test_failure", "testing"
        )
        assert parsed is not None
        assert parsed.agrees_with_primary == ValidationVerdict.INSUFFICIENT_INFORMATION
        assert parsed.confidence_level == ConfidenceLevel.INSUFFICIENT_DATA
        assert meta["schema_valid"] is False
        assert meta["parse_strategy"] == "degraded_fallback"
        assert meta["failure_type"] == "test_failure"

    def test_degraded_fallback_research(self):
        """Degraded fallback for ResearchSummary has safe defaults."""
        from libs.ai.providers.base import BaseAIProvider
        parsed, meta = BaseAIProvider._make_degraded_fallback(
            ResearchSummary, {}, "test_failure", "testing"
        )
        assert parsed is not None
        assert parsed.confidence_level == ConfidenceLevel.INSUFFICIENT_DATA
        assert parsed.thesis_type.value == "unclear"
        assert meta["schema_valid"] is False

    def test_degraded_never_high_confidence(self):
        """Degraded fallback NEVER produces high confidence output."""
        from libs.ai.providers.base import BaseAIProvider
        for schema in [ValidationSummary, ResearchSummary]:
            parsed, _ = BaseAIProvider._make_degraded_fallback(schema, {}, "x", "x")
            if parsed:
                assert parsed.confidence_level != ConfidenceLevel.HIGH
                assert parsed.confidence_level != ConfidenceLevel.MEDIUM

    def test_degraded_validation_never_agrees(self):
        """Degraded ValidationSummary NEVER says 'agree'."""
        from libs.ai.providers.base import BaseAIProvider
        parsed, _ = BaseAIProvider._make_degraded_fallback(ValidationSummary, {}, "x", "x")
        assert parsed.agrees_with_primary != ValidationVerdict.AGREE


# ─── End-to-end integration ───

class TestEndToEndParsing:
    """Simulates real Gemini output patterns."""

    def test_gemini_typical_output(self):
        """Gemini often wraps JSON in explanation text."""
        raw = """Based on my analysis of the primary research, here is my validation:

```json
{
  "agrees_with_primary": "agree_with_reservations",
  "agreement_points": ["Strong AI market position", "Revenue growth trajectory"],
  "disagreement_points": ["Valuation risk understated"],
  "overlooked_risks": ["Geopolitical supply chain risk", "Customer concentration"],
  "unsupported_claims": [],
  "additional_considerations": ["Margin sustainability needs monitoring"],
  "recommendation": "The primary analysis is directionally sound but should weight valuation risk more heavily.",
  "confidence_level": "medium"
}
```

Note: This validation is based on publicly available information only."""

        json_str = _extract_json_from_text(raw)
        import json
        data = json.loads(json_str)
        data = _normalize_schema_data(data, ValidationSummary)
        parsed = ValidationSummary.model_validate(data)

        assert parsed.agrees_with_primary == ValidationVerdict.AGREE_WITH_RESERVATIONS
        assert len(parsed.overlooked_risks) == 2
        assert parsed.confidence_level == ConfidenceLevel.MEDIUM

    def test_gemini_no_fence_output(self):
        """Gemini sometimes returns bare JSON without fences."""
        raw = """{"agrees_with_primary":"disagree","disagreement_points":["Thesis too optimistic given macro headwinds","Revenue growth projections lack support"],"overlooked_risks":["Interest rate environment impact","Margin compression risk"],"unsupported_claims":["Market share gains assumed without evidence"],"additional_considerations":[],"recommendation":"Significantly reduce conviction level and add macro overlay analysis.","confidence_level":"medium"}"""

        json_str = _extract_json_from_text(raw)
        import json
        data = json.loads(json_str)
        parsed = ValidationSummary.model_validate(data)
        assert parsed.agrees_with_primary == ValidationVerdict.DISAGREE
        assert len(parsed.disagreement_points) == 2

    def test_provider_empty_response(self):
        """Empty provider response triggers degraded fallback."""
        from libs.ai.providers.base import BaseAIProvider
        parsed, meta = BaseAIProvider._make_degraded_fallback(
            ValidationSummary, {}, "empty_response", "Provider returned empty content"
        )
        assert meta["failure_type"] == "empty_response"
        assert parsed.confidence_level == ConfidenceLevel.INSUFFICIENT_DATA
