"""
OpenRouter via OpenAI-compatible SDK (https://openrouter.ai/docs).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import structlog
from openai import OpenAI

from app.config import settings

logger = structlog.get_logger()


def create_openrouter_client() -> Optional[OpenAI]:
    if not getattr(settings, "OPENROUTER_API_KEY", None):
        return None
    base = (settings.OPENROUTER_BASE_URL or "https://openrouter.ai/api/v1").rstrip("/")
    headers: Dict[str, str] = {"X-Title": "NewsFlow"}
    ref = getattr(settings, "OPENROUTER_HTTP_REFERER", None) or ""
    if ref.strip():
        headers["HTTP-Referer"] = ref.strip()
    client = OpenAI(
        api_key=settings.OPENROUTER_API_KEY,
        base_url=base,
        default_headers=headers,
    )
    logger.info("openrouter_client_ready", base_url=base)
    return client


def chat_completion_text(
    client: OpenAI,
    model: str,
    messages: List[Dict[str, Any]],
    *,
    max_tokens: int,
    temperature: float,
) -> str:
    resp = client.chat.completions.create(
        model=model,
        messages=messages,
        max_tokens=max_tokens,
        temperature=temperature,
    )
    return (resp.choices[0].message.content or "").strip()
