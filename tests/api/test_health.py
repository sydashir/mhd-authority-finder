"""/health proves the API is up AND can reach Postgres (ADR-014)."""

from httpx import AsyncClient


async def test_health_reports_db_ok(client: AsyncClient) -> None:
    resp = await client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["database"] == "ok"


async def test_openapi_schema_is_served(client: AsyncClient) -> None:
    resp = await client.get("/openapi.json")
    assert resp.status_code == 200
    schema = resp.json()
    assert schema["openapi"].startswith("3.")
    assert "/health" in schema["paths"]
