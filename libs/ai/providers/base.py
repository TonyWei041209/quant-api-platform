"""Abstract base for AI model providers."""
from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any, Optional, Type
from pydantic import BaseModel
import json
import re
import time
import structlog

logger = structlog.get_logger(__name__)


def _extract_json_from_text(text: str) -> str:
    """Extract JSON from model output that may contain markdown fences or surrounding text.

    Layered extraction strategy:
    1. Strip code fences (```json, ```JSON, ```, etc.)
    2. Find first { ... } or [ ... ] block via bracket matching
    3. Return cleaned text for json.loads
    """
    if not text or not text.strip():
        raise ValueError("Empty text — nothing to extract")

    s = text.strip()

    # Layer 1: Strip markdown code fences (case-insensitive)
    fence_pattern = re.compile(r"```(?:json|JSON|jsonc)?\s*\n?(.*?)```", re.DOTALL)
    fence_match = fence_pattern.search(s)
    if fence_match:
        s = fence_match.group(1).strip()

    # Layer 2: Try direct parse first (fastest path)
    try:
        json.loads(s)
        return s
    except json.JSONDecodeError:
        pass

    # Layer 3: Find first { ... } or [ ... ] block via bracket matching
    for start_char, end_char in [('{', '}'), ('[', ']')]:
        start_idx = s.find(start_char)
        if start_idx == -1:
            continue
        depth = 0
        in_string = False
        escape_next = False
        for i in range(start_idx, len(s)):
            c = s[i]
            if escape_next:
                escape_next = False
                continue
            if c == '\\' and in_string:
                escape_next = True
                continue
            if c == '"' and not escape_next:
                in_string = not in_string
                continue
            if in_string:
                continue
            if c == start_char:
                depth += 1
            elif c == end_char:
                depth -= 1
                if depth == 0:
                    candidate = s[start_idx:i + 1]
                    try:
                        json.loads(candidate)
                        return candidate
                    except json.JSONDecodeError:
                        # Try light repair before giving up on this candidate
                        repaired = _light_json_repair(candidate)
                        try:
                            json.loads(repaired)
                            return repaired
                        except json.JSONDecodeError:
                            break  # This block didn't work, try next

    # Layer 4: Light repair on full text (trailing commas, etc.)
    repaired = _light_json_repair(s)
    try:
        json.loads(repaired)
        return repaired
    except json.JSONDecodeError:
        pass

    raise ValueError(f"No valid JSON found in text (length={len(text)})")


def _light_json_repair(text: str) -> str:
    """Safe, minimal JSON repair for common LLM output quirks.

    Only fixes:
    - Trailing commas before } or ]
    - Single-line // comments
    Does NOT attempt creative reconstruction.
    """
    # Remove single-line comments (outside strings — simplified)
    result = re.sub(r'//[^\n]*', '', text)
    # Remove trailing commas: ,] or ,}
    result = re.sub(r',\s*([}\]])', r'\1', result)
    return result.strip()


def _normalize_enum_value(value: Any, enum_type: type) -> Any:
    """Normalize enum values with case-insensitive matching and common aliases."""
    if not isinstance(value, str):
        return value
    lower = value.strip().lower().replace(' ', '_').replace('-', '_')
    # Try direct match first
    for member in enum_type:
        if member.value == lower:
            return member.value
    # Try name match
    for member in enum_type:
        if member.name.lower() == lower:
            return member.value
    return value  # Return original if no match — let Pydantic handle the error


def _normalize_schema_data(data: dict, schema: Type[BaseModel]) -> dict:
    """Normalize parsed JSON data to match schema expectations.

    Handles:
    - Case-insensitive enum values
    - Snake_case / camelCase key normalization
    - None -> [] for list fields
    - None -> "" for string fields
    """
    if not isinstance(data, dict):
        return data

    fields = schema.model_fields
    normalized = {}

    # Build case-insensitive key map
    key_map = {}
    for field_name in fields:
        key_map[field_name.lower()] = field_name
        # Also map camelCase variants
        camel = re.sub(r'_([a-z])', lambda m: m.group(1).upper(), field_name)
        key_map[camel.lower()] = field_name

    for k, v in data.items():
        # Normalize key
        norm_key = key_map.get(k.lower().replace('-', '_'), k)

        # Normalize value based on field type
        if norm_key in fields:
            field_info = fields[norm_key]
            annotation = field_info.annotation

            # Handle enum normalization
            from enum import EnumType
            origin = getattr(annotation, '__origin__', None)
            if isinstance(annotation, EnumType):
                v = _normalize_enum_value(v, annotation)
            # Handle Optional[EnumType]
            elif origin is type(None) or str(annotation).startswith('typing.Optional'):
                args = getattr(annotation, '__args__', ())
                for arg in args:
                    if isinstance(arg, EnumType):
                        v = _normalize_enum_value(v, arg)
                        break

            # None -> empty list for list fields
            if v is None and (str(annotation).startswith('list') or (origin and origin is list)):
                v = []

            # None -> "" for string fields
            if v is None and annotation is str:
                v = ""

        normalized[norm_key] = v

    return normalized


class BaseAIProvider(ABC):
    """Base class for AI model providers (OpenAI, Gemini, etc.)."""

    @property
    @abstractmethod
    def provider_name(self) -> str: ...

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        *,
        model: str,
        system_prompt: str = "",
        temperature: float = 0.3,
        max_tokens: int = 2000,
        response_schema: Optional[Type[BaseModel]] = None,
        timeout: float = 60.0,
    ) -> dict[str, Any]:
        """Generate a completion. Returns dict with 'content', 'usage', 'model'."""
        ...

    async def generate_structured(
        self,
        prompt: str,
        response_schema: Type[BaseModel],
        *,
        model: str,
        system_prompt: str = "",
        temperature: float = 0.2,
        max_tokens: int = 3000,
        timeout: float = 60.0,
    ) -> tuple[Optional[BaseModel], dict[str, Any]]:
        """Generate and parse into a Pydantic model.

        Layered parsing strategy:
        1. Strict JSON parse
        2. Code fence extraction + parse
        3. Bracket-matched JSON extraction from mixed text
        4. Light JSON repair (trailing commas, comments)
        5. Schema normalization (enum case, key case, None -> default)
        6. Degraded fallback with explicit reliability marking

        Returns (parsed_model_or_None, metadata_dict).
        """
        start = time.time()
        try:
            result = await self.generate(
                prompt,
                model=model,
                system_prompt=system_prompt,
                temperature=temperature,
                max_tokens=max_tokens,
                response_schema=response_schema,
                timeout=timeout,
            )
            content = result.get("content", "")
            usage = result.get("usage", {})
            latency_ms = int((time.time() - start) * 1000)

            base_meta = {"usage": usage, "latency_ms": latency_ms, "raw_content": content}

            # --- Layered parsing ---
            if not content or not content.strip():
                logger.warning("ai.empty_response", provider=self.provider_name, model=model)
                return self._make_degraded_fallback(
                    response_schema, base_meta, "empty_response", "Provider returned empty content"
                )

            # Step 1-4: Extract and parse JSON
            try:
                json_str = _extract_json_from_text(content)
                data = json.loads(json_str)
            except (ValueError, json.JSONDecodeError) as extract_err:
                logger.warning("ai.json_extraction_failed",
                               provider=self.provider_name, model=model,
                               error=str(extract_err), content_length=len(content))
                return self._make_degraded_fallback(
                    response_schema, base_meta, "json_extraction_failed", str(extract_err)
                )

            # Step 5: Schema normalization
            if isinstance(data, dict):
                data = _normalize_schema_data(data, response_schema)

            # Step 6: Pydantic validation
            try:
                parsed = response_schema.model_validate(data)
                return parsed, {**base_meta, "schema_valid": True, "parse_strategy": "structured"}
            except Exception as validate_err:
                logger.warning("ai.schema_validation_failed",
                               provider=self.provider_name, model=model,
                               error=str(validate_err))
                # Try lenient validation (allow extra fields, coerce types)
                try:
                    parsed = response_schema.model_validate(data, strict=False)
                    return parsed, {**base_meta, "schema_valid": True,
                                    "parse_strategy": "normalized", "validation_note": str(validate_err)}
                except Exception:
                    return self._make_degraded_fallback(
                        response_schema, base_meta, "schema_validation_failed", str(validate_err)
                    )

        except Exception as e:
            latency_ms = int((time.time() - start) * 1000)
            logger.error("ai.generate_failed", provider=self.provider_name, model=model, error=str(e))
            return None, {"latency_ms": latency_ms, "schema_valid": False, "error": str(e)}

    @staticmethod
    def _make_degraded_fallback(
        schema: Type[BaseModel],
        base_meta: dict,
        failure_type: str,
        failure_detail: str,
    ) -> tuple[Optional[BaseModel], dict]:
        """Create a degraded fallback that does NOT fabricate conclusions.

        Returns a minimal valid object with explicitly low confidence
        and clear degraded markers. Never produces pseudo-certain output.
        """
        meta = {
            **base_meta,
            "schema_valid": False,
            "parse_strategy": "degraded_fallback",
            "failure_type": failure_type,
            "failure_detail": failure_detail,
        }

        try:
            # Build minimal safe defaults — explicitly low-confidence
            safe_defaults = {}
            fields = schema.model_fields
            for name, field in fields.items():
                annotation = field.annotation
                # Force low confidence / insufficient data for any confidence/verdict fields
                if "confidence" in name.lower():
                    safe_defaults[name] = "insufficient_data"
                elif "agrees" in name.lower() or "verdict" in name.lower():
                    safe_defaults[name] = "insufficient_information"
                elif "thesis_type" in name.lower():
                    safe_defaults[name] = "unclear"
                # Provide safe defaults for required string fields (no default in schema)
                elif field.is_required() and annotation is str:
                    safe_defaults[name] = "[parse failed — no data available]"

            parsed = schema.model_validate(safe_defaults)
            return parsed, meta
        except Exception:
            return None, meta
