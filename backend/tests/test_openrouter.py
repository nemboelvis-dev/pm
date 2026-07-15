import asyncio
import json
import re
from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi.testclient import TestClient

from app import openrouter


def test_connectivity_requires_authentication(client: TestClient) -> None:
    assert client.post("/api/ai/connectivity").status_code == 401


def test_missing_api_key_returns_clear_server_error(
    authenticated_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

    response = authenticated_client.post("/api/ai/connectivity")

    assert response.status_code == 503
    assert response.json() == {
        "detail": "OPENROUTER_API_KEY is not configured on the server"
    }


def test_connectivity_returns_model_and_reply_without_a_live_call(
    authenticated_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def fake_completion(_: object) -> str:
        return "4"

    monkeypatch.setattr(openrouter, "create_completion", fake_completion)

    response = authenticated_client.post("/api/ai/connectivity")

    assert response.status_code == 200
    assert response.json() == {"model": openrouter.OPENROUTER_MODEL, "reply": "4"}


def test_client_sends_the_expected_openrouter_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-secret-key")

    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == openrouter.OPENROUTER_URL
        assert request.headers["Authorization"] == "Bearer test-secret-key"
        assert request.headers["X-OpenRouter-Title"] == "Project Management MVP"
        assert json.loads(request.content) == {
            "model": "openai/gpt-oss-120b",
            "messages": [{"role": "user", "content": "What is 2+2?"}],
            "temperature": 0,
            "max_tokens": 64,
        }
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "4"}}]},
        )

    async def run() -> str:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await openrouter.create_completion(
                [{"role": "user", "content": "What is 2+2?"}], client=client
            )

    assert asyncio.run(run()) == "4"


def test_client_forwards_structured_output_requirements(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-secret-key")
    response_format = {
        "type": "json_schema",
        "json_schema": {
            "name": "test",
            "strict": True,
            "schema": {"type": "object", "additionalProperties": False},
        },
    }

    async def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert payload["response_format"] == response_format
        assert payload["provider"] == {"require_parameters": True}
        assert payload["max_tokens"] == 1000
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": '{"ok":true}'}}]},
        )

    async def run() -> str:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await openrouter.create_completion(
                [{"role": "user", "content": "Return JSON"}],
                client=client,
                response_format=response_format,
                max_tokens=1000,
            )

    assert asyncio.run(run()) == '{"ok":true}'


def test_client_retries_a_retryable_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-secret-key")
    sleep = AsyncMock()
    monkeypatch.setattr(openrouter.asyncio, "sleep", sleep)
    attempts = 0

    async def handler(_: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return httpx.Response(503, headers={"Retry-After": "0"})
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "Recovered"}}]},
        )

    async def run() -> str:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await openrouter.create_completion([], client=client)

    assert asyncio.run(run()) == "Recovered"
    assert attempts == 2
    sleep.assert_awaited_once_with(0)


def test_client_stops_after_the_bounded_retry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-secret-key")
    monkeypatch.setattr(openrouter.asyncio, "sleep", AsyncMock())
    attempts = 0

    async def handler(_: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(502, headers={"Retry-After": "0"})

    async def run() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            with pytest.raises(
                openrouter.OpenRouterRequestError,
                match="OpenRouter request failed with HTTP 502",
            ):
                await openrouter.create_completion([], client=client)

    asyncio.run(run())
    assert attempts == openrouter.MAX_ATTEMPTS


@pytest.mark.parametrize(
    ("response", "message"),
    [
        (
            httpx.Response(401, json={"error": {"message": "test-secret-key"}}),
            "OpenRouter request failed with HTTP 401",
        ),
        (
            httpx.Response(200, json={"choices": []}),
            "OpenRouter returned an invalid response",
        ),
    ],
)
def test_client_sanitizes_openrouter_failures(
    response: httpx.Response,
    message: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-secret-key")

    async def handler(_: httpx.Request) -> httpx.Response:
        return response

    async def run() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            with pytest.raises(openrouter.OpenRouterRequestError, match=message) as error:
                await openrouter.create_completion([], client=client)
            assert "test-secret-key" not in str(error.value)

    asyncio.run(run())


@pytest.mark.live
def test_live_openrouter_connectivity() -> None:
    reply = asyncio.run(
        openrouter.create_completion(
            [{"role": "user", "content": "What is 2+2? Reply with only the number."}]
        )
    )

    assert re.search(r"\b4\b", reply)
