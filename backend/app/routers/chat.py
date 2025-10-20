"""
Chat assistant (OpenRouter) for the NewsFlow FAB widget.
"""

from fastapi import APIRouter, HTTPException
from openai import (
    APIConnectionError,
    APIStatusError,
    AuthenticationError,
    BadRequestError,
    RateLimitError,
)
from starlette import status as http_status
import structlog

from app.config import settings
from app.models import ChatRequest, ChatResponse
from app.services.chat_service import chat_service

logger = structlog.get_logger()

router = APIRouter(prefix="/api/v1/chat", tags=["chat"])


def _openrouter_error_message(exc: BaseException) -> str:
    """Best-effort user-facing text from an OpenAI/OpenRouter SDK error."""
    body = getattr(exc, "body", None)
    if isinstance(body, dict):
        err = body.get("error")
        if isinstance(err, dict):
            msg = err.get("message")
            if isinstance(msg, str) and msg.strip():
                return msg.strip()[:500]
    s = str(exc).strip()
    return s[:500] if s else "Request failed."


@router.post("", response_model=ChatResponse)
async def chat_completion(body: ChatRequest) -> ChatResponse:
    """
    Multiturn chat with optional images (data URLs) and optional voice (`input_audio` via OpenRouter).
    Last message in `messages` must be from the user.
    """
    if not settings.openrouter_enabled or not chat_service.is_configured():
        raise HTTPException(
            status_code=http_status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Chat is unavailable: set OPENROUTER_API_KEY on the server.",
        )

    if len(body.messages) > settings.CHAT_MAX_MESSAGES:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=f"Too many messages (max {settings.CHAT_MAX_MESSAGES}).",
        )

    if body.messages[-1].role != "user":
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail="The last message must be from the user.",
        )

    try:
        data = await chat_service.complete(body)
    except ValueError as e:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
    except AuthenticationError as e:
        logger.warning("chat_openrouter_auth_failed", error=str(e))
        raise HTTPException(
            status_code=http_status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "OpenRouter rejected the API key (401). Set a valid OPENROUTER_API_KEY in backend/.env "
                "and restart the API server."
            ),
        ) from e
    except RateLimitError as e:
        logger.warning("chat_openrouter_rate_limit", error=str(e))
        raise HTTPException(
            status_code=http_status.HTTP_429_TOO_MANY_REQUESTS,
            detail="OpenRouter rate limit reached. Wait a minute and try again.",
        ) from e
    except BadRequestError as e:
        msg = _openrouter_error_message(e)
        logger.warning("chat_openrouter_bad_request", error=str(e), message=msg)
        raise HTTPException(
            status_code=http_status.HTTP_502_BAD_GATEWAY,
            detail=f"OpenRouter: {msg}",
        ) from e
    except APIConnectionError as e:
        logger.error("chat_openrouter_connection", error=str(e))
        raise HTTPException(
            status_code=http_status.HTTP_502_BAD_GATEWAY,
            detail="Could not reach OpenRouter. Check your network connection.",
        ) from e
    except APIStatusError as e:
        msg = _openrouter_error_message(e)
        logger.error("chat_openrouter_api_status", status=getattr(e, "status_code", None), error=str(e))
        raise HTTPException(
            status_code=http_status.HTTP_502_BAD_GATEWAY,
            detail=f"OpenRouter: {msg}",
        ) from e
    except Exception as e:
        logger.error("chat_completion_failed", error=str(e))
        raise HTTPException(
            status_code=http_status.HTTP_502_BAD_GATEWAY,
            detail="The assistant could not complete this request. Try again later.",
        ) from e

    return ChatResponse(success=True, data=data)
