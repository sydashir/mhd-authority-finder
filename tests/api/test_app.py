"""App-level concerns: CORS (the React dev origin must be allowed, with credentials)
and the auto-generated docs (ADR-014)."""

from httpx import AsyncClient


async def test_cors_allows_configured_origin(client: AsyncClient) -> None:
    resp = await client.get("/health", headers={"Origin": "http://localhost:5173"})
    assert resp.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert resp.headers["access-control-allow-credentials"] == "true"


async def test_cors_preflight_is_answered(client: AsyncClient) -> None:
    resp = await client.options(
        "/prospects",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert resp.status_code == 200
    assert resp.headers["access-control-allow-origin"] == "http://localhost:5173"


async def test_swagger_docs_served(client: AsyncClient) -> None:
    resp = await client.get("/docs")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
