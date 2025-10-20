"""
NewsFlow chat assistant (OpenRouter): text, images, and voice via input_audio (e.g. Nemotron Omni).
See https://openrouter.ai/docs/guides/overview/multimodal/audio
"""

from __future__ import annotations

import asyncio
import base64
import binascii
import re
from typing import Any, Dict, List, Optional, Tuple

import structlog
from openai import OpenAI

from app.config import settings
from app.models import ChatHistoryMessage, ChatRequest, ChatResultData
from app.services.llm_openrouter import chat_completion_text, create_openrouter_client

logger = structlog.get_logger()

_SYSTEM = (
    "You are NewsFlow's in-app assistant. Help with technology, IT news, and using the NewsFlow "
    "aggregator. Be clear and concise unless the user asks for depth. Match the user's language "
    "(Korean, English, etc.) when they write in one primary language."
)


def _split_data_url(s: str) -> Tuple[Optional[str], str]:
    s = (s or "").strip()
    m = re.match(r"^data:([^;]+);base64,(.+)$", s, re.DOTALL)
    if m:
        return m.group(1).strip(), m.group(2).strip()
    return None, s


def _normalize_images(urls: Optional[List[str]]) -> List[str]:
    if not urls:
        return []
    max_k = settings.CHAT_MAX_KEYFRAMES
    max_b = settings.CHAT_MAX_IMAGE_BYTES
    out: List[str] = []
    for u in urls[:max_k]:
        mime, payload = _split_data_url(u)
        try:
            raw = base64.b64decode(payload, validate=False)
        except (binascii.Error, ValueError):
            logger.warning("chat_image_base64_invalid")
            continue
        if len(raw) > max_b:
            logger.warning("chat_image_too_large", size=len(raw))
            continue
        if mime and mime.startswith("image/"):
            b64 = base64.standard_b64encode(raw).decode("ascii")
            out.append(f"data:{mime};base64,{b64}")
        elif mime is None:
            b64 = base64.standard_b64encode(raw).decode("ascii")
            out.append(f"data:image/jpeg;base64,{b64}")
        else:
            logger.warning("chat_image_bad_mime", mime=mime)
    return out


def _decode_audio(b64: Optional[str]) -> Optional[bytes]:
    if not b64 or not str(b64).strip():
        return None
    s = str(b64).strip()
    if s.startswith("data:") and "base64," in s:
        s = s.split("base64,", 1)[1]
    try:
        raw = base64.b64decode(s, validate=False)
    except (binascii.Error, ValueError):
        return None
    if len(raw) > settings.CHAT_MAX_AUDIO_BYTES:
        return None
    return raw if raw else None


def _audio_format_from_mime(mime: Optional[str]) -> str:
    """OpenRouter input_audio.format — see supported list in OpenRouter audio docs."""
    m = (mime or "audio/wav").lower().split(";")[0].strip()
    if m in ("audio/wav", "audio/x-wav", "audio/wave"):
        return "wav"
    if "webm" in m:
        return "webm"
    if "wav" in m:
        return "wav"
    if "mpeg" in m or m == "audio/mp3":
        return "mp3"
    if "mp4" in m or m == "audio/mp4" or m == "audio/x-m4a":
        return "m4a"
    if "ogg" in m:
        return "ogg"
    if "flac" in m:
        return "flac"
    if "aac" in m:
        return "aac"
    if "aiff" in m or m == "audio/x-aiff":
        return "aiff"
    if "pcm" in m:
        return "pcm16"
    return "webm"


class ChatService:
    """OpenRouter-backed chat for the FAB widget."""

    def __init__(self) -> None:
        self._client: Optional[OpenAI] = create_openrouter_client()

    def is_configured(self) -> bool:
        return self._client is not None

    def _pick_model(self, has_images: bool, has_audio: bool) -> str:
        if has_audio:
            return settings.OPENROUTER_CHAT_AUDIO_MODEL
        if has_images:
            return settings.OPENROUTER_CHAT_VISION_MODEL
        return settings.OPENROUTER_CHAT_TEXT_MODEL or settings.OPENROUTER_MODEL

    def _build_messages(
        self,
        history: List[ChatHistoryMessage],
        images: List[str],
        last_user_text: str,
        audio_b64: Optional[str],
        audio_format: str,
    ) -> List[Dict[str, Any]]:
        msgs: List[Dict[str, Any]] = [{"role": "system", "content": _SYSTEM}]
        last_idx = len(history) - 1

        for i, turn in enumerate(history):
            if turn.role == "assistant":
                msgs.append({"role": "assistant", "content": turn.text or ""})
                continue
            is_last = i == last_idx
            text_for_turn = (last_user_text if is_last else (turn.text or "")).strip()

            if is_last and (images or audio_b64):
                parts: List[Dict[str, Any]] = []
                cap = text_for_turn or (
                    "The user attached media (images and/or voice). Answer helpfully in text."
                )
                parts.append({"type": "text", "text": cap})
                for url in images:
                    parts.append({"type": "image_url", "image_url": {"url": url}})
                if audio_b64:
                    parts.append(
                        {
                            "type": "input_audio",
                            "input_audio": {
                                "data": audio_b64,
                                "format": audio_format,
                            },
                        }
                    )
                msgs.append({"role": "user", "content": parts})
            else:
                msgs.append({"role": "user", "content": text_for_turn})
        return msgs

    def complete_sync(self, request: ChatRequest) -> ChatResultData:
        if not self._client:
            raise RuntimeError("OpenRouter API not configured")

        history = request.messages[-settings.CHAT_MAX_MESSAGES :]
        if not history:
            raise ValueError("No messages")
        if history[-1].role != "user":
            raise ValueError("Last message must be from the user")

        images = _normalize_images(request.images)
        audio_raw = _decode_audio(request.audio_base64)
        audio_b64: Optional[str] = None
        audio_format = "webm"
        if audio_raw:
            audio_b64 = base64.standard_b64encode(audio_raw).decode("ascii")
            audio_format = _audio_format_from_mime(request.audio_mime)

        last_user = history[-1].text or ""
        if not last_user.strip() and not images and not audio_b64:
            raise ValueError("Send a message, image, or voice note")

        if audio_b64 and not last_user.strip() and not images:
            last_user = (
                "The user sent a voice message. Listen and reply helpfully in the same language "
                "when possible."
            )

        has_images = bool(images)
        has_audio = bool(audio_b64)
        if request.images and not images and not last_user.strip() and not has_audio:
            raise ValueError("No valid images after validation")

        model = self._pick_model(has_images, has_audio)
        msgs = self._build_messages(history, images, last_user, audio_b64, audio_format)

        out_text = chat_completion_text(
            self._client,
            model,
            msgs,
            max_tokens=settings.CHAT_MAX_TOKENS,
            temperature=settings.CHAT_TEMPERATURE,
        )
        out_text = out_text.strip() or "…"
        return ChatResultData(message=out_text, model=model)

    async def complete(self, request: ChatRequest) -> ChatResultData:
        return await asyncio.to_thread(self.complete_sync, request)


chat_service = ChatService()
