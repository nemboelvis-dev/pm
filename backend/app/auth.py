import base64
import binascii
import hashlib
import hmac
import os
import time
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, HTTPException, Request, Response, status
from pydantic import BaseModel

from app.database import connect, verify_password

SESSION_COOKIE = "pm_session"
SESSION_MAX_AGE = 30 * 24 * 60 * 60

router = APIRouter(prefix="/api/auth", tags=["authentication"])


class Credentials(BaseModel):
    username: str
    password: str


class User(BaseModel):
    username: str


def create_session_token(username: str, expires_at: int | None = None) -> str:
    expires_at = expires_at or int(time.time()) + SESSION_MAX_AGE
    payload = f"{username}:{expires_at}"
    signature = hmac.new(
        _session_secret(), payload.encode(), hashlib.sha256
    ).hexdigest()
    token = base64.urlsafe_b64encode(f"{payload}:{signature}".encode()).decode()
    return token.rstrip("=")


def read_session_token(token: str | None) -> str | None:
    if not token:
        return None

    try:
        padded_token = token + "=" * (-len(token) % 4)
        username, expires_at_value, signature = (
            base64.urlsafe_b64decode(padded_token).decode().split(":", 2)
        )
        expires_at = int(expires_at_value)
    except (binascii.Error, UnicodeDecodeError, ValueError):
        return None

    payload = f"{username}:{expires_at}"
    expected_signature = hmac.new(
        _session_secret(), payload.encode(), hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(signature, expected_signature):
        return None
    if not username or expires_at <= int(time.time()):
        return None
    return username


def authenticated_user(request: Request) -> User:
    username = read_session_token(request.cookies.get(SESSION_COOKIE))
    with connect() as connection:
        user_exists = username and connection.execute(
            "SELECT 1 FROM users WHERE username = ?", (username,)
        ).fetchone()
    if not user_exists:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )
    return User(username=username)


@router.post("/login", response_model=User)
def login(credentials: Credentials, response: Response) -> User:
    with connect() as connection:
        user = connection.execute(
            "SELECT username, password_hash FROM users WHERE username = ?",
            (credentials.username,),
        ).fetchone()
    if not user or not verify_password(credentials.password, user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    response.set_cookie(
        key=SESSION_COOKIE,
        value=create_session_token(user["username"]),
        max_age=SESSION_MAX_AGE,
        expires=datetime.now(UTC) + timedelta(seconds=SESSION_MAX_AGE),
        httponly=True,
        samesite="lax",
    )
    return User(username=user["username"])


@router.get("/session", response_model=User)
def session(request: Request) -> User:
    return authenticated_user(request)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(response: Response) -> None:
    response.delete_cookie(key=SESSION_COOKIE, httponly=True, samesite="lax")


def _session_secret() -> bytes:
    return os.getenv("SESSION_SECRET", "local-project-management-secret").encode()
