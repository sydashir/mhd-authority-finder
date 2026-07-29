"""App authentication (ADR-026): local username + password, no third-party identity.

Replaces the Google sign-in of ADR-018. Teams were unwilling to hand a Google account
to the tool, and a Google project + per-teammate test-user allowlist is heavy machinery
for a handful of internal users. Credentials live in ``AUTH_USERS`` as
``username:<scrypt hash>`` pairs; the plaintext password is never stored or logged.

Everything downstream is unchanged: a successful login mints the same signed app-session
JWT carried in the same httpOnly cookie, and ``get_current_user`` still guards the data
routes. The pipeline, CLI, and scheduler never touch the HTTP API, so they are unaffected.
"""

import base64
import hashlib
import secrets
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Annotated

import jwt
from fastapi import Depends, HTTPException, Request, status
from pydantic import BaseModel

if TYPE_CHECKING:
    from authority_finder.config import Settings

SESSION_COOKIE = "session"
_ALGORITHM = "HS256"

# scrypt parameters (RFC 7914). n=2**14 with r=8/p=1 is the interactive-login preset:
# ~16MB of memory per attempt, which makes offline brute force expensive while keeping
# a real login well under 100ms.
_SCRYPT_N = 16384
_SCRYPT_R = 8
_SCRYPT_P = 1
_SALT_BYTES = 16
_KEY_BYTES = 32
_SCHEME = "scrypt"
_ENCODED_PARTS = 6

# Verifying against this costs the same as a real hash, so an unknown username takes the
# same time as a wrong password (no user enumeration by timing).
_DUMMY_HASH = (
    f"{_SCHEME}${_SCRYPT_N}${_SCRYPT_R}${_SCRYPT_P}$"
    "AAAAAAAAAAAAAAAAAAAAAA==$AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="
)


class AuthUser(BaseModel):
    """The signed-in user. ``username`` is the identity recorded on outreach edits."""

    username: str
    name: str = ""


class AuthError(Exception):
    """A session token could not be verified."""


def _derive(password: str, salt: bytes, *, n: int, r: int, p: int) -> bytes:
    return hashlib.scrypt(password.encode(), salt=salt, n=n, r=r, p=p, dklen=_KEY_BYTES)


def hash_password(password: str) -> str:
    """Hash a password for storage: ``scrypt$n$r$p$<salt b64>$<key b64>``.

    A fresh random salt per call, so identical passwords never share a hash.
    """
    salt = secrets.token_bytes(_SALT_BYTES)
    key = _derive(password, salt, n=_SCRYPT_N, r=_SCRYPT_R, p=_SCRYPT_P)
    return "$".join(
        [
            _SCHEME,
            str(_SCRYPT_N),
            str(_SCRYPT_R),
            str(_SCRYPT_P),
            base64.b64encode(salt).decode(),
            base64.b64encode(key).decode(),
        ]
    )


def verify_password(password: str, encoded: str) -> bool:
    """Constant-time check of ``password`` against a stored hash. Malformed → ``False``."""
    parts = encoded.split("$")
    if len(parts) != _ENCODED_PARTS or parts[0] != _SCHEME:
        return False
    try:
        n, r, p = int(parts[1]), int(parts[2]), int(parts[3])
        salt = base64.b64decode(parts[4], validate=True)
        expected = base64.b64decode(parts[5], validate=True)
        candidate = _derive(password, salt, n=n, r=r, p=p)
    except (ValueError, TypeError):
        return False
    return secrets.compare_digest(candidate, expected)


def parse_users(entries: list[str]) -> dict[str, str]:
    """``["admin:scrypt$..."]`` → ``{"admin": "scrypt$..."}``.

    Split on the FIRST colon only: the hash itself contains ``$`` and base64.
    """
    users: dict[str, str] = {}
    for entry in entries:
        username, separator, encoded = entry.strip().partition(":")
        if not separator or not username.strip() or not encoded.strip():
            continue
        users[username.strip().lower()] = encoded.strip()
    return users


def authenticate(username: str, password: str, users: dict[str, str]) -> AuthUser | None:
    """The signed-in user for these credentials, or ``None``.

    An unknown username still runs a verify against a dummy hash so the work (and so the
    response time) does not reveal which usernames exist.
    """
    name = username.strip().lower()
    encoded = users.get(name)
    if verify_password(password, encoded if encoded is not None else _DUMMY_HASH):
        return AuthUser(username=name, name=name) if encoded is not None else None
    return None


def mint_session(user: AuthUser, *, secret: str, hours: int) -> str:
    """A signed app-session JWT (HS256) — the app's own session."""
    now = datetime.now(UTC)
    payload = {
        "sub": user.username,
        "username": user.username,
        "name": user.name,
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
    except jwt.PyJWTError as exc:
        # PyJWTError (not just InvalidTokenError) so a key problem surfaces as 401, not 500.
        raise AuthError("invalid session") from exc
    return AuthUser(username=str(claims.get("username", "")), name=str(claims.get("name", "")))


def get_current_user(request: Request) -> AuthUser:
    """Dependency: the signed-in user from the session cookie, or 401."""
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "not authenticated")
    settings: Settings = request.app.state.settings
    try:
        return decode_session(token, secret=settings.jwt_secret.get_secret_value())
    except AuthError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, str(exc)) from exc


CurrentUser = Annotated[AuthUser, Depends(get_current_user)]

# (username, password) -> user or None. Injectable so tests can swap the credential source.
Authenticator = Callable[[str, str], AuthUser | None]
