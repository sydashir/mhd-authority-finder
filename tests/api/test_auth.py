"""Auth routes (ADR-026): password sign-in, session cookie, guarded routes, lockout.

No third party is involved, so these exercise the REAL credential path end to end:
a real scrypt hash in settings, a real login, the real cookie, the real guard.
"""

from collections.abc import AsyncGenerator

import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from pydantic import SecretStr

from authority_finder.config import Settings
from backend.app import create_app
from backend.auth import SESSION_COOKIE, AuthUser, hash_password, mint_session

PASSWORD = "adminuser123"
Client = tuple[AsyncClient, FastAPI]


def _settings() -> Settings:
    return Settings(
        cors_allow_origins=["http://localhost:5173"],
        jwt_secret=SecretStr("test-secret-0123456789-abcdefghij"),
        auth_users=[f"admin:{hash_password(PASSWORD)}"],
        auth_max_failed_logins=3,
        auth_lockout_minutes=15,
    )


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[Client]:
    app = create_app(_settings())
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac, app


async def test_login_sets_a_session_cookie_and_returns_the_user(client: Client) -> None:
    ac, _ = client
    resp = await ac.post("/auth/login", json={"username": "admin", "password": PASSWORD})
    assert resp.status_code == 200
    assert resp.json()["username"] == "admin"
    assert SESSION_COOKIE in resp.cookies
    assert "httponly" in resp.headers["set-cookie"].lower()  # never readable by scripts


async def test_login_is_case_insensitive_on_username(client: Client) -> None:
    ac, _ = client
    resp = await ac.post("/auth/login", json={"username": "ADMIN", "password": PASSWORD})
    assert resp.status_code == 200


async def test_wrong_password_is_401_and_sets_no_cookie(client: Client) -> None:
    ac, _ = client
    resp = await ac.post("/auth/login", json={"username": "admin", "password": "wrong"})
    assert resp.status_code == 401
    assert SESSION_COOKIE not in resp.cookies


async def test_unknown_user_gets_the_same_message_as_a_wrong_password(client: Client) -> None:
    # Identical responses, or the form tells an attacker which usernames exist.
    ac, _ = client
    bad_pw = await ac.post("/auth/login", json={"username": "admin", "password": "wrong"})
    no_user = await ac.post("/auth/login", json={"username": "ghost", "password": "wrong"})
    assert bad_pw.status_code == no_user.status_code == 401
    assert bad_pw.json()["detail"] == no_user.json()["detail"]


async def test_repeated_failures_lock_the_client_out(client: Client) -> None:
    ac, _ = client
    for _ in range(3):  # auth_max_failed_logins
        assert (
            await ac.post("/auth/login", json={"username": "admin", "password": "wrong"})
        ).status_code == 401
    locked = await ac.post("/auth/login", json={"username": "admin", "password": PASSWORD})
    assert locked.status_code == 429  # even the CORRECT password is refused while locked
    assert "too many" in locked.json()["detail"].lower()


async def test_successful_login_clears_the_failure_count(client: Client) -> None:
    ac, _ = client
    await ac.post("/auth/login", json={"username": "admin", "password": "wrong"})
    await ac.post("/auth/login", json={"username": "admin", "password": PASSWORD})
    # Two more failures would trip the limit if the counter had not been reset.
    for _ in range(2):
        assert (
            await ac.post("/auth/login", json={"username": "admin", "password": "wrong"})
        ).status_code == 401


async def test_me_requires_a_session_and_returns_the_user(client: Client) -> None:
    ac, _ = client
    assert (await ac.get("/auth/me")).status_code == 401
    await ac.post("/auth/login", json={"username": "admin", "password": PASSWORD})
    me = await ac.get("/auth/me")
    assert me.status_code == 200
    assert me.json()["username"] == "admin"


async def test_logout_clears_the_session(client: Client) -> None:
    ac, _ = client
    await ac.post("/auth/login", json={"username": "admin", "password": PASSWORD})
    assert (await ac.post("/auth/logout")).status_code == 200
    assert (await ac.get("/auth/me")).status_code == 401


async def test_data_routes_are_guarded(client: Client) -> None:
    ac, _ = client
    for path in ("/prospects", "/runs", "/stats"):
        assert (await ac.get(path)).status_code == 401


async def test_a_forged_session_cookie_is_rejected(client: Client) -> None:
    ac, _ = client
    ac.cookies.set(SESSION_COOKIE, "not.a.jwt")
    assert (await ac.get("/auth/me")).status_code == 401
    # ...and one signed with the WRONG secret is rejected too.
    forged = mint_session(AuthUser(username="admin"), secret="attacker-secret", hours=1)
    ac.cookies.set(SESSION_COOKIE, forged)
    assert (await ac.get("/auth/me")).status_code == 401
