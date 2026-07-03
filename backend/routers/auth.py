"""Auth endpoints (ADR-018): Google sign-in, current user, logout.

``POST /auth/google`` and ``GET /health`` are the only public routes; everything
else requires a session. The Google verifier is a dependency so tests can inject
a fake and never call Google.
"""

import asyncio
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel

from authority_finder.config import Settings
from backend.auth import (
    SESSION_COOKIE,
    AuthError,
    AuthUser,
    CurrentUser,
    GoogleVerifier,
    is_allowed,
    mint_session,
    verify_google_id_token,
)

router = APIRouter(prefix="/auth", tags=["auth"])


class GoogleLoginBody(BaseModel):
    credential: str  # the ID token from @react-oauth/google's <GoogleLogin> onSuccess


def _settings(request: Request) -> Settings:
    return request.app.state.settings


def get_verifier(request: Request) -> GoogleVerifier:
    """The real Google verifier bound to our client id; overridden in tests."""
    client_id = _settings(request).google_oauth_client_id

    def _verify(credential: str) -> AuthUser:
        return verify_google_id_token(credential, client_id)

    return _verify


VerifierDep = Annotated[GoogleVerifier, Depends(get_verifier)]


@router.post("/google", response_model=AuthUser)
async def login_google(
    body: GoogleLoginBody, request: Request, response: Response, verify: VerifierDep
) -> AuthUser:
    """Verify the Google token server-side, enforce the allowlist, set a session cookie."""
    try:
        user = await asyncio.to_thread(verify, body.credential)  # blocking cert I/O
    except AuthError as exc:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, "Google sign-in could not be verified"
        ) from exc

    settings = _settings(request)
    if not is_allowed(user.email, settings.allowed_emails):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "This account isn't authorized — contact your admin."
        )

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
