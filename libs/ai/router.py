"""Three-lane AI model router for quant research workflows."""
from __future__ import annotations
from typing import Optional, Type
from pydantic import BaseModel
import time
import structlog

from libs.ai.providers.base import BaseAIProvider
from libs.ai.providers.openai_provider import OpenAIProvider
from libs.ai.providers.gemini_provider import GeminiProvider
from libs.ai.schemas import AICallLog

logger = structlog.get_logger(__name__)

# Lane definitions
LANE_CONFIG = {
    "cheap_preprocess": {
        "provider": "gemini",
        "model": "gemini-2.0-flash-lite",
        "description": "Cheap text preprocessing, summarization, classification",
    },
    "primary_research": {
        "provider": "openai",
        "model": "gpt-4o",
        "description": "Deep research analysis, thesis generation, risk narrative",
    },
    "validation": {
        "provider": "gemini",
        "model": "gemini-2.5-pro",
        "description": "Second-opinion validation, thesis checking, risk review",
    },
}

# Singleton providers
_providers: dict[str, BaseAIProvider] = {}

def _get_provider(name: str) -> BaseAIProvider:
    if name not in _providers:
        if name == "openai":
            _providers[name] = OpenAIProvider()
        elif name == "gemini":
            _providers[name] = GeminiProvider()
        else:
            raise ValueError(f"Unknown provider: {name}")
    return _providers[name]

# Call log history (in-memory for now, could be persisted)
_call_logs: list[AICallLog] = []

def get_recent_logs(limit: int = 20) -> list[AICallLog]:
    return _call_logs[-limit:]

async def route_call(
    lane: str,
    prompt: str,
    *,
    system_prompt: str = "",
    response_schema: Optional[Type[BaseModel]] = None,
    temperature: Optional[float] = None,
    max_tokens: int = 2000,
    timeout: float = 60.0,
) -> tuple[Optional[BaseModel], dict]:
    """Route an AI call through the appropriate lane.

    Returns (parsed_model_or_None, metadata_dict).
    """
    if lane not in LANE_CONFIG:
        raise ValueError(f"Unknown lane: {lane}. Available: {list(LANE_CONFIG.keys())}")

    config = LANE_CONFIG[lane]
    provider = _get_provider(config["provider"])
    model = config["model"]
    temp = temperature if temperature is not None else (0.2 if lane == "validation" else 0.3)

    start = time.time()

    try:
        if response_schema:
            parsed, meta = await provider.generate_structured(
                prompt,
                response_schema,
                model=model,
                system_prompt=system_prompt,
                temperature=temp,
                max_tokens=max_tokens,
                timeout=timeout,
            )
        else:
            result = await provider.generate(
                prompt,
                model=model,
                system_prompt=system_prompt,
                temperature=temp,
                max_tokens=max_tokens,
                timeout=timeout,
            )
            parsed = None
            meta = {"usage": result.get("usage", {}), "raw_content": result.get("content", "")}

        latency_ms = int((time.time() - start) * 1000)
        usage = meta.get("usage", {})

        log = AICallLog(
            provider=config["provider"],
            model=model,
            lane=lane,
            prompt_tokens=usage.get("prompt_tokens"),
            completion_tokens=usage.get("completion_tokens"),
            total_tokens=usage.get("total_tokens"),
            latency_ms=latency_ms,
            success=True,
            schema_valid=meta.get("schema_valid", True),
        )
        _call_logs.append(log)
        if len(_call_logs) > 100:
            _call_logs.pop(0)

        logger.info("ai.call_complete", lane=lane, provider=config["provider"], model=model, latency_ms=latency_ms, tokens=usage.get("total_tokens"))

        return parsed, {**meta, "latency_ms": latency_ms, "lane": lane, "provider": config["provider"], "model": model}

    except Exception as e:
        latency_ms = int((time.time() - start) * 1000)
        log = AICallLog(
            provider=config["provider"],
            model=model,
            lane=lane,
            latency_ms=latency_ms,
            success=False,
            schema_valid=False,
            error_message=str(e),
        )
        _call_logs.append(log)
        logger.error("ai.call_failed", lane=lane, provider=config["provider"], model=model, error=str(e))
        return None, {"error": str(e), "latency_ms": latency_ms, "lane": lane, "provider": config["provider"], "model": model}
