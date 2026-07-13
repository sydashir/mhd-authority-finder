"""Auth (ADR-018): server-side Google-token verification, email allowlist, and a
signed app-session JWT in an httpOnly cookie. Google is mocked (an injected
verifier / a monkeypatched verify call) — these assert OUR logic, not Google's.
"""

from collections.abc import AsyncGenerator, Callable
from datetime import UTC, datetime, timedelta

import jwt
import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from pydantic import SecretStr
from sqlalchemy.ext.asyncio import AsyncSession

from authority_finder.config import Settings
from authority_finder.db.models import SourceTag, TrustBand
from authority_finder.db.repository import ProspectIn, upsert_prospect
from backend import auth as auth_mod
from backend.app import create_app
from backend.auth import (
    AuthError,
    AuthUser,
    decode_session,
    is_allowed,
    mint_session,
    verify_google_id_token,
)
from backend.deps import get_session
from backend.routers.auth import get_verifier

_SECRET = "test-secret-0123456789-abcdefghij"


def _claims(**over: object) -> dict[str, object]:
    base: dict[str, object] = {
        "iss": "https://accounts.google.com",
        "aud": "client-123",
        "sub": "google-sub-1",
        "email": "User@Example.com",
        "email_verified": True,
        "name": "Test User",
        "picture": "https://pic",
        "exp": 9999999999,
    }
    base.update(over)
    return base


def _stub(claims: dict[str, object]) -> Callable[..., dict[str, object]]:
    """A fake for google id_token.verify_oauth2_token returning fixed claims."""

    def _verify(*_a: object, **_k: object) -> dict[str, object]:
        return claims

    return _verify


# ---- core: verify_google_id_token ----------------------------------------------


def test_verify_returns_user_and_lowercases_email(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(auth_mod.id_token, "verify_oauth2_token", _stub(_claims()))
    user = verify_google_id_token("tok", "client-123")
    assert user.email == "user@example.com"  # lowercased
    assert user.name == "Test User"
    assert user.sub == "google-sub-1"


def test_verify_rejects_unverified_email(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        auth_mod.id_token, "verify_oauth2_token", _stub(_claims(email_verified=False))
    )
    with pytest.raises(AuthError):
        verify_google_id_token("tok", "client-123")


def test_verify_rejects_bad_issuer(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(auth_mod.id_token, "verify_oauth2_token", _stub(_claims(iss="evil.com")))
    with pytest.raises(AuthError):
        verify_google_id_token("tok", "client-123")


def test_verify_maps_library_valueerror_to_autherror(monkeypatch: pytest.MonkeyPatch) -> None:
    def _boom(*_a: object, **_k: object) -> dict[str, object]:
        raise ValueError("bad audience")

    monkeypatch.setattr(auth_mod.id_token, "verify_oauth2_token", _boom)
    with pytest.raises(AuthError):
        verify_google_id_token("tok", "client-123")


# ---- core: allowlist + session jwt ---------------------------------------------


def test_is_allowed_is_case_insensitive() -> None:
    assert is_allowed("Jake@X.com", ["jake@x.com"])
    assert not is_allowed("nope@x.com", ["jake@x.com"])


def test_session_round_trip() -> None:
    user = AuthUser(email="a@b.com", name="A", picture="p", sub="s1")
    token = mint_session(user, secret=_SECRET, hours=1)
    back = decode_session(token, secret=_SECRET)
    assert back.email == "a@b.com"
    assert back.name == "A"
    assert back.sub == "s1"


def test_decode_rejects_tampered_token() -> None:
    token = mint_session(AuthUser(email="a@b.com"), secret=_SECRET, hours=1)
    with pytest.raises(AuthError):
        decode_session(token, secret="a-different-secret-0123456789-abcdef")


def test_decode_rejects_expired_token() -> None:
    past = datetime.now(UTC) - timedelta(hours=1)
    token = jwt.encode({"email": "a@b.com", "exp": past}, _SECRET, algorithm="HS256")
    with pytest.raises(AuthError):
        decode_session(token, secret=_SECRET)


# ---- routes --------------------------------------------------------------------


def _settings() -> Settings:
    return Settings(
        cors_allow_origins=["http://localhost:5173"],
        allowed_emails=["allowed@example.com"],
        jwt_secret=SecretStr(_SECRET),
        auth_session_hours=1,
    )


@pytest_asyncio.fixture
async def auth_client(session: AsyncSession) -> AsyncGenerator[tuple[AsyncClient, FastAPI]]:
    app = create_app(_settings())

    async def _override_session() -> AsyncGenerator[AsyncSession]:
        yield session

    app.dependency_overrides[get_session] = _override_session  # data routes reach the test DB
    # NOTE: get_current_user is NOT overridden here — we test the real auth behavior.
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac, app
    app.dependency_overrides.clear()


def _use_verifier(app: FastAPI, user_or_error: AuthUser | Exception) -> None:
    def fake(_credential: str) -> AuthUser:
        if isinstance(user_or_error, Exception):
            raise user_or_error
        return user_or_error

    app.dependency_overrides[get_verifier] = lambda: fake


async def test_login_allowed_sets_cookie_and_returns_user(
    auth_client: tuple[AsyncClient, FastAPI],
) -> None:
    client, app = auth_client
    _use_verifier(app, AuthUser(email="allowed@example.com", name="Al", sub="s"))

    resp = await client.post("/auth/google", json={"credential": "tok"})
    assert resp.status_code == 200
    assert resp.json()["email"] == "allowed@example.com"
    assert "session=" in resp.headers.get("set-cookie", "")


async def test_login_non_allowlisted_is_403(auth_client: tuple[AsyncClient, FastAPI]) -> None:
    client, app = auth_client
    _use_verifier(app, AuthUser(email="stranger@example.com"))

    resp = await client.post("/auth/google", json={"credential": "tok"})
    assert resp.status_code == 403
    assert "authorized" in resp.json()["detail"].lower()


async def test_login_invalid_token_is_401(auth_client: tuple[AsyncClient, FastAPI]) -> None:
    client, app = auth_client
    _use_verifier(app, AuthError("bad token"))

    resp = await client.post("/auth/google", json={"credential": "tok"})
    assert resp.status_code == 401


async def test_me_requires_session(auth_client: tuple[AsyncClient, FastAPI]) -> None:
    client, _app = auth_client
    assert (await client.get("/auth/me")).status_code == 401


async def test_login_then_me_then_logout(auth_client: tuple[AsyncClient, FastAPI]) -> None:
    client, app = auth_client
    _use_verifier(app, AuthUser(email="allowed@example.com", name="Al"))

    await client.post("/auth/google", json={"credential": "tok"})  # sets cookie on the client jar
    me = await client.get("/auth/me")
    assert me.status_code == 200
    assert me.json()["email"] == "allowed@example.com"

    await client.post("/auth/logout")
    assert (await client.get("/auth/me")).status_code == 401


async def test_data_route_guarded(
    auth_client: tuple[AsyncClient, FastAPI], session: AsyncSession
) -> None:
    client, app = auth_client
    await upsert_prospect(
        session,
        ProspectIn(
            website="a.gov",
            specific_page="https://a.gov/x",
            email="",
            phone="",
            contact_source="",
            contact_trust=TrustBand.high,
            organization_description="",
            geo_served="G",
            population=None,
            competitor_links="—",
            source_tag=SourceTag.MHD,
            confidence=TrustBand.high,
            date_added=datetime.now(UTC).date(),
        ),
    )
    await session.commit()

    assert (await client.get("/prospects")).status_code == 401  # no session
    # the outreach write is guarded too — no session, no mutating the team's data
    assert (
        await client.patch("/prospects/1/outreach", json={"status": "contacted"})
    ).status_code == 401

    _use_verifier(app, AuthUser(email="allowed@example.com"))
    await client.post("/auth/google", json={"credential": "tok"})
    assert (await client.get("/prospects")).status_code == 200  # authed
