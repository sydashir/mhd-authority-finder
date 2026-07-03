"""App authentication (ADR-018): verify a Google ID token SERVER-SIDE, enforce an
email allowlist, and carry a signed app-session JWT in an httpOnly cookie.

The pipeline, CLI, and scheduler are separate entry points that never touch the
HTTP API, so they are unaffected — auth guards only the API's data routes.
"""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Annotated, Any

import jwt
from fastapi import Depends, HTTPException, Request, status
from google.auth.exceptions import GoogleAuthError
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token
from pydantic import BaseModel

if TYPE_CHECKING:
    from authority_finder.config import Settings

SESSION_COOKIE = "session"
_ALGORITHM = "HS256"
_ACCEPTED_ISSUERS = {"accounts.google.com", "https://accounts.google.com"}
# google-auth ships no stubs; alias its module behind Any so the dynamic call surface
# doesn't leak "unknown type" errors (same pattern as the Sheets writer).
_id_token: Any = id_token
# One transport, reused: it caches Google's public signing certs (per Cache-Control).
_GOOGLE_REQUEST = google_requests.Request()


class AuthUser(BaseModel):
    """The signed-in user (from a verified Google token, then from our session JWT)."""

    email: str
    name: str = ""
    picture: str = ""
    sub: str = ""


class AuthError(Exception):
    """A Google credential or session token could not be verified."""


def verify_google_id_token(credential: str, client_id: str) -> AuthUser:
    """Verify a Google ID token against Google's keys and our client id (audience).

    google-auth validates the RS256 signature, ``aud == client_id``, and ``exp``;
    we additionally enforce a trusted issuer and ``email_verified``. Raises
    :class:`AuthError` on any failure (the route maps it to 401). Does BLOCKING
    cert I/O — call it via ``asyncio.to_thread`` from an async route.
    """
    try:
        claims = _id_token.verify_oauth2_token(
            credential, _GOOGLE_REQUEST, client_id, clock_skew_in_seconds=10
        )
    except (ValueError, GoogleAuthError) as exc:
        # ValueError: bad signature / wrong audience / expired.
        # GoogleAuthError: wrong issuer (NOT a ValueError subclass — catch both).
        raise AuthError(str(exc)) from exc

    if claims.get("iss") not in _ACCEPTED_ISSUERS:
        raise AuthError("untrusted token issuer")
    if claims.get("email_verified") is not True:
        raise AuthError("email not verified")
    email = str(claims.get("email", "")).strip().lower()
    if not email:
        raise AuthError("token carries no email")

    return AuthUser(
        email=email,
        name=str(claims.get("name", "")),
        picture=str(claims.get("picture", "")),
        sub=str(claims.get("sub", "")),
    )


def is_allowed(email: str, allowed: list[str]) -> bool:
    """The allowlist gate — a verified email must be explicitly listed."""
    return email.strip().lower() in allowed


def mint_session(user: AuthUser, *, secret: str, hours: int) -> str:
    """A signed app-session JWT (HS256) — the app's own session, not Google's token."""
    now = datetime.now(UTC)
    payload = {
        "sub": user.sub or user.email,
        "email": user.email,
        "name": user.name,
        "picture": user.picture,
        "iat": now,
        "exp": now + timedelta(hours=hours),
    }
    return jwt.encode(payload, secret, algorithm=_ALGORITHM)


def decode_session(token: str, *, secret: str) -> AuthUser:
    """Decode + validate an app-session JWT (signature + expiry). Raises AuthError."""
    try:
        claims = jwt.decode(token, secret, algorithms=[_ALGORITHM], options={"require": ["exp"]})
    except jwt.ExpiredSignatureError as exc:
        raise AuthError("session expired") from exc
    except jwt.InvalidTokenError as exc:
        raise AuthError("invalid session") from exc
    return AuthUser(
        email=str(claims.get("email", "")),
        name=str(claims.get("name", "")),
        picture=str(claims.get("picture", "")),
        sub=str(claims.get("sub", "")),
    )


def get_current_user(request: Request) -> AuthUser:
    """Dependency: the signed-in user from the session cookie (Bearer fallback), or 401."""
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        header = request.headers.get("Authorization", "")
        if header.startswith("Bearer "):
            token = header.removeprefix("Bearer ")
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "not authenticated")
    settings: Settings = request.app.state.settings
    try:
        return decode_session(token, secret=settings.jwt_secret.get_secret_value())
    except AuthError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, str(exc)) from exc


CurrentUser = Annotated[AuthUser, Depends(get_current_user)]

# (email, name, picture) verifier — injectable so tests don't hit Google.
GoogleVerifier = Callable[[str], AuthUser]
