"""Abstract base for AI model providers."""
from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any, Optional, Type
from pydantic import BaseModel
import time
import structlog

logger = structlog.get_logger(__name__)

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
        """Generate and parse into a Pydantic model. Returns (parsed_model, raw_metadata)."""
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

            # Try to parse structured output
            import json
            try:
                # Try to extract JSON from content
                json_str = content
                if "```json" in json_str:
                    json_str = json_str.split("```json")[1].split("```")[0].strip()
                elif "```" in json_str:
                    json_str = json_str.split("```")[1].split("```")[0].strip()

                data = json.loads(json_str)
                parsed = response_schema.model_validate(data)
                return parsed, {"usage": usage, "latency_ms": latency_ms, "schema_valid": True, "raw_content": content}
            except (json.JSONDecodeError, Exception) as parse_err:
                logger.warning("ai.parse_failed", provider=self.provider_name, model=model, error=str(parse_err))
                # Try to construct a minimal valid object
                try:
                    parsed = response_schema.model_validate({})
                    return parsed, {"usage": usage, "latency_ms": latency_ms, "schema_valid": False, "raw_content": content, "parse_error": str(parse_err)}
                except Exception:
                    return None, {"usage": usage, "latency_ms": latency_ms, "schema_valid": False, "raw_content": content, "parse_error": str(parse_err)}
        except Exception as e:
            latency_ms = int((time.time() - start) * 1000)
            logger.error("ai.generate_failed", provider=self.provider_name, model=model, error=str(e))
            return None, {"latency_ms": latency_ms, "schema_valid": False, "error": str(e)}
