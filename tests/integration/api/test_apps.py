import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_create_application(client: AsyncClient):
    response = await client.post(
        "/api/v1/apps/",
        json={"name": "integration-test-app"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "integration-test-app"
    assert "api_key" in data
    assert "id" in data

@pytest.mark.asyncio
async def test_create_duplicate_application(client: AsyncClient):
    # First creation
    await client.post(
        "/api/v1/apps/",
        json={"name": "duplicate-app"}
    )
    # Second creation (should fail)
    response = await client.post(
        "/api/v1/apps/",
        json={"name": "duplicate-app"}
    )
    assert response.status_code == 400
