import asyncio
import logging
import os
from collections.abc import Sequence

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.auth import User, authenticated_user


OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_MODEL = "openai/gpt-oss-120b"
RETRYABLE_STATUS_CODES = {429, 502, 503}
MAX_ATTEMPTS = 2

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ai", tags=["ai"])


class OpenRouterConfigurationError(RuntimeError):
    pass


class OpenRouterRequestError(RuntimeError):
    pass


class ConnectivityResponse(BaseModel):
    model: str
    reply: str


async def create_completion(
    messages: Sequence[dict[str, str]],
    *,
    client: httpx.AsyncClient | None = None,
    response_format: dict[str, object] | None = None,
    max_tokens: int = 64,
) -> str:
    api_key = os.getenv("OPENROUTER_API_KEY", "").strip()
    if not api_key:
        raise OpenRouterConfigurationError(
            "OPENROUTER_API_KEY is not configured on the server"
        )

    owns_client = client is None
    request_client = client or httpx.AsyncClient(timeout=60)
    payload: dict[str, object] = {
        "model": OPENROUTER_MODEL,
        "messages": list(messages),
        "temperature": 0,
        "max_tokens": max_tokens,
    }
    if response_format:
        payload["response_format"] = response_format
        payload["provider"] = {"require_parameters": True}

    response: httpx.Response | None = None
    try:
        for attempt in range(MAX_ATTEMPTS):
            try:
                response = await request_client.post(
                    OPENROUTER_URL,
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                        "X-OpenRouter-Title": "Project Management MVP",
                    },
                    json=payload,
                )
            except httpx.HTTPError as error:
                if attempt + 1 == MAX_ATTEMPTS:
                    raise OpenRouterRequestError(
                        "Unable to reach OpenRouter"
                    ) from error
                logger.warning("Retrying OpenRouter after a network error")
                await asyncio.sleep(0.5)
                continue

            if (
                response.status_code not in RETRYABLE_STATUS_CODES
                or attempt + 1 == MAX_ATTEMPTS
            ):
                break
            delay = _retry_delay(response.headers.get("Retry-After"))
            logger.warning(
                "Retrying OpenRouter after HTTP %s",
                response.status_code,
            )
            await asyncio.sleep(delay)
    finally:
        if owns_client:
            await request_client.aclose()

    if response is None:
        raise OpenRouterRequestError("Unable to reach OpenRouter")
    if response.is_error:
        raise OpenRouterRequestError(
            f"OpenRouter request failed with HTTP {response.status_code}"
        )

    try:
        content = response.json()["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError, ValueError) as error:
        raise OpenRouterRequestError("OpenRouter returned an invalid response") from error

    if not isinstance(content, str) or not content.strip():
        raise OpenRouterRequestError("OpenRouter returned an empty response")
    return content.strip()


def _retry_delay(retry_after: str | None) -> float:
    if retry_after is None:
        return 0.5
    try:
        return min(max(float(retry_after), 0), 10)
    except ValueError:
        return 0.5


@router.post("/connectivity", response_model=ConnectivityResponse)
async def connectivity(
    _: User = Depends(authenticated_user),
) -> ConnectivityResponse:
    try:
        reply = await create_completion(
            [{"role": "user", "content": "What is 2+2? Reply with only the number."}]
        )
    except OpenRouterConfigurationError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(error),
        ) from error
    except OpenRouterRequestError as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(error),
        ) from error

    return ConnectivityResponse(model=OPENROUTER_MODEL, reply=reply)
