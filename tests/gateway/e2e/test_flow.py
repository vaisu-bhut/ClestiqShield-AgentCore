import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_full_flow_e2e(client: AsyncClient):
    """
    Simulate a full user journey:
    1. Create App
    2. Get API Key
    3. Use Proxy
    """
    # 1. Create App
    app_name = "e2e-app"
    create_res = await client.post(
        "/api/v1/apps/",
        json={"name": app_name}
    )
    assert create_res.status_code == 200
    api_key = create_res.json()["api_key"]

    # 2. Use Proxy
    proxy_res = await client.post(
        "/api/v1/proxy/",
        headers={"X-API-Key": api_key},
        json={"query": "test e2e"}
    )
    assert proxy_res.status_code == 200
    assert proxy_res.json()["app"] == app_name
