import logging
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.auth import SESSION_COOKIE, create_session_token
from app.database import connect
from app.main import app, warn_if_static_directory_missing

def test_health(client: TestClient) -> None:
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_hello(client: TestClient) -> None:
    response = client.get("/api/hello")

    assert response.status_code == 200
    assert response.json() == {"message": "Hello from FastAPI"}


def test_frontend_is_mounted_after_api_routes() -> None:
    assert app.routes[-1].name == "frontend"


def test_missing_static_directory_logs_a_warning(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    missing_directory = tmp_path / "missing-static"

    with caplog.at_level(logging.WARNING):
        warn_if_static_directory_missing(missing_directory)

    assert str(missing_directory) in caplog.text


def test_session_requires_authentication(client: TestClient) -> None:
    response = client.get("/api/auth/session")

    assert response.status_code == 401
    assert response.json() == {"detail": "Authentication required"}


def test_login_rejects_invalid_credentials(client: TestClient) -> None:
    response = client.post(
        "/api/auth/login",
        json={"username": "user", "password": "wrong"},
    )

    assert response.status_code == 401
    assert SESSION_COOKIE not in client.cookies


def test_login_verifies_the_stored_password_hash(client: TestClient) -> None:
    with connect() as connection:
        connection.execute(
            "UPDATE users SET password_hash = 'invalid' WHERE username = 'user'"
        )

    response = client.post(
        "/api/auth/login",
        json={"username": "user", "password": "password"},
    )

    assert response.status_code == 401


def test_login_sets_persistent_httponly_cookie(client: TestClient) -> None:
    response = client.post(
        "/api/auth/login",
        json={"username": "user", "password": "password"},
    )

    cookie = response.headers["set-cookie"].lower()
    assert response.status_code == 200
    assert response.json() == {"username": "user"}
    assert f"{SESSION_COOKIE}=" in cookie
    assert "max-age=2592000" in cookie
    assert "expires=" in cookie
    assert "httponly" in cookie
    assert "samesite=lax" in cookie


def test_cookie_authenticates_a_new_client(client: TestClient) -> None:
    client.post(
        "/api/auth/login",
        json={"username": "user", "password": "password"},
    )
    cookie = client.cookies[SESSION_COOKIE]

    with TestClient(app) as restarted_client:
        restarted_client.cookies.set(SESSION_COOKIE, cookie)
        response = restarted_client.get("/api/auth/session")

    assert response.status_code == 200
    assert response.json() == {"username": "user"}


def test_tampered_malformed_and_expired_tokens_are_rejected(
    client: TestClient,
) -> None:
    token = create_session_token("user")
    client.cookies.set(SESSION_COOKIE, f"{token[:-1]}x")
    assert client.get("/api/auth/session").status_code == 401

    client.cookies.set(SESSION_COOKIE, "not-base64")
    assert client.get("/api/auth/session").status_code == 401

    client.cookies.set(SESSION_COOKIE, create_session_token("user", expires_at=1))
    assert client.get("/api/auth/session").status_code == 401


def test_logout_clears_the_cookie(client: TestClient) -> None:
    client.post(
        "/api/auth/login",
        json={"username": "user", "password": "password"},
    )

    response = client.post("/api/auth/logout")

    assert response.status_code == 204
    assert SESSION_COOKIE not in client.cookies
    assert client.get("/api/auth/session").status_code == 401
