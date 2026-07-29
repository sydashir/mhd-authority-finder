"""Auth endpoints (ADR-026): password sign-in, current user, logout.

``POST /auth/login`` and ``GET /health`` are the only public routes; everything else
requires a session. Sign-in failures are throttled per client, because a password form
is brute-forceable in a way a third-party identity provider was not.
"""

import time
from dataclasses import dataclass, field

from fastapi import APIRouter, HTTPException, Request, Response, status
from pydantic import BaseModel, Field

from authority_finder.config import Settings
from backend.auth import (
    SESSION_COOKIE,
    AuthUser,
    CurrentUser,
    authenticate,
    mint_session,
    parse_users,
)

router = APIRouter(prefix="/auth", tags=["auth"])

# One message for every failure mode, so the form never reveals which usernames exist.
_REJECTED = "Incorrect username or password."


class LoginBody(BaseModel):
    username: str = Field(max_length=64)
    password: str = Field(max_length=256)


@dataclass
class _Attempts:
    """In-process failed-login counter. Per worker: a restart clears it, and a multi-worker
    deploy throttles per worker. That is acceptable for an internal tool of a few users;
    a shared store (Redis) is the upgrade if this ever faces the open internet."""

    failures: dict[str, tuple[int, float]] = field(default_factory=dict[str, tuple[int, float]])

    def locked_for(self, key: str, *, limit: int, window_s: float) -> float:
        count, first_at = self.failures.get(key, (0, 0.0))
        if count < limit:
            return 0.0
        remaining = window_s - (time.monotonic() - first_at)
        if remaining <= 0:
            self.failures.pop(key, None)  # window elapsed, start fresh
            return 0.0
        return remaining

    def record_failure(self, key: str, *, window_s: float) -> None:
        count, first_at = self.failures.get(key, (0, 0.0))
        now = time.monotonic()
        if count == 0 or now - first_at > window_s:
            self.failures[key] = (1, now)
        else:
            self.failures[key] = (count + 1, first_at)

    def clear(self, key: str) -> None:
        self.failures.pop(key, None)


def _settings(request: Request) -> Settings:
    return request.app.state.settings


def _attempts_for(request: Request) -> _Attempts:
    """The failed-login counter, stored per app instance (not module-global, so tests and
    multiple apps in one process never share a lockout)."""
    store: _Attempts | None = getattr(request.app.state, "login_attempts", None)
    if store is None:
        store = _Attempts()
        request.app.state.login_attempts = store
    return store


def _client_key(request: Request, username: str) -> str:
    host = request.client.host if request.client else "unknown"
    return f"{host}:{username.strip().lower()}"


@router.post("/login", response_model=AuthUser)
async def login(body: LoginBody, request: Request, response: Response) -> AuthUser:
    """Verify credentials against ``AUTH_USERS`` and set the session cookie."""
    settings = _settings(request)
    attempts = _attempts_for(request)
    window_s = settings.auth_lockout_minutes * 60
    key = _client_key(request, body.username)

    locked = attempts.locked_for(key, limit=settings.auth_max_failed_logins, window_s=window_s)
    if locked > 0:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            f"Too many failed attempts. Try again in {int(locked // 60) + 1} minutes.",
        )

    user = authenticate(body.username, body.password, parse_users(settings.auth_users))
    if user is None:
        attempts.record_failure(key, window_s=window_s)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, _REJECTED)

    attempts.clear(key)
    token = mint_session(
        user, secret=settings.jwt_secret.get_secret_value(), hours=settings.auth_session_hours
    )
    response.set_cookie(
        SESSION_COOKIE,
        token,
        httponly=True,
        samesite="lax",  # localhost:5173 <-> :8000 is same-site, so Lax flows the cookie
        secure=settings.auth_cookie_secure,  # True in prod/https
        max_age=settings.auth_session_hours * 3600,
        path="/",
    )
    return user


@router.get("/me", response_model=AuthUser)
async def me(user: CurrentUser) -> AuthUser:
    return user


@router.post("/logout")
async def logout(request: Request, response: Response) -> dict[str, bool]:
    response.delete_cookie(
        SESSION_COOKIE,
        path="/",
        samesite="lax",
        secure=_settings(request).auth_cookie_secure,
        httponly=True,
    )
    return {"ok": True}
