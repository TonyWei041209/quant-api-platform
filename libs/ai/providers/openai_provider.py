"""OpenAI provider (GPT-5.4 etc.)."""
from __future__ import annotations
from typing import Any, Optional, Type
from pydantic import BaseModel
import httpx
import os
import structlog

from libs.ai.providers.base import BaseAIProvider

logger = structlog.get_logger(__name__)

class OpenAIProvider(BaseAIProvider):
    """OpenAI API provider."""

    @property
    def provider_name(self) -> str:
        return "openai"

    def _get_api_key(self) -> str:
        key = os.getenv("OPENAI_API_KEY", "")
        if not key:
            raise ValueError("OPENAI_API_KEY not configured")
        return key

    async def generate(
        self,
        prompt: str,
        *,
        model: str = "gpt-4o",
        system_prompt: str = "",
        temperature: float = 0.3,
        max_tokens: int = 2000,
        response_schema: Optional[Type[BaseModel]] = None,
        timeout: float = 60.0,
    ) -> dict[str, Any]:
        api_key = self._get_api_key()

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        user_content = prompt
        if response_schema:
            schema_hint = f"\n\nRespond ONLY with valid JSON matching this schema:\n{response_schema.model_json_schema()}"
            user_content += schema_hint

        messages.append({"role": "user", "content": user_content})

        body = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json=body,
            )
            resp.raise_for_status()
            data = resp.json()

        choice = data["choices"][0]
        usage = data.get("usage", {})

        return {
            "content": choice["message"]["content"],
            "model": data.get("model", model),
            "usage": {
                "prompt_tokens": usage.get("prompt_tokens"),
                "completion_tokens": usage.get("completion_tokens"),
                "total_tokens": usage.get("total_tokens"),
            },
        }
