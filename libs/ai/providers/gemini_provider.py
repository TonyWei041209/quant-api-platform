"""Google Gemini provider (2.5 Pro, 2.5 Flash-Lite, etc.)."""
from __future__ import annotations
from typing import Any, Optional, Type
from pydantic import BaseModel
import httpx
import os
import structlog

from libs.ai.providers.base import BaseAIProvider

logger = structlog.get_logger(__name__)

class GeminiProvider(BaseAIProvider):
    """Google Gemini API provider."""

    @property
    def provider_name(self) -> str:
        return "gemini"

    def _get_api_key(self) -> str:
        key = os.getenv("GEMINI_API_KEY", "")
        if not key:
            raise ValueError("GEMINI_API_KEY not configured")
        return key

    async def generate(
        self,
        prompt: str,
        *,
        model: str = "gemini-2.5-pro",
        system_prompt: str = "",
        temperature: float = 0.3,
        max_tokens: int = 2000,
        response_schema: Optional[Type[BaseModel]] = None,
        timeout: float = 60.0,
    ) -> dict[str, Any]:
        api_key = self._get_api_key()

        contents = []

        user_content = prompt
        if response_schema:
            schema_hint = f"\n\nRespond ONLY with valid JSON matching this schema:\n{response_schema.model_json_schema()}"
            user_content += schema_hint

        contents.append({"role": "user", "parts": [{"text": user_content}]})

        body = {
            "contents": contents,
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
                "responseMimeType": "application/json" if response_schema else "text/plain",
            },
        }

        if system_prompt:
            body["systemInstruction"] = {"parts": [{"text": system_prompt}]}

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"

        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(url, json=body)
            resp.raise_for_status()
            data = resp.json()

        # Parse Gemini response
        candidates = data.get("candidates", [])
        if not candidates:
            raise ValueError(f"Gemini returned no candidates: {data}")

        content = ""
        parts = candidates[0].get("content", {}).get("parts", [])
        for part in parts:
            content += part.get("text", "")

        usage_meta = data.get("usageMetadata", {})

        return {
            "content": content,
            "model": model,
            "usage": {
                "prompt_tokens": usage_meta.get("promptTokenCount"),
                "completion_tokens": usage_meta.get("candidatesTokenCount"),
                "total_tokens": usage_meta.get("totalTokenCount"),
            },
        }
