import pytest
from httpx import AsyncClient
from unittest.mock import patch, AsyncMock, MagicMock

@pytest.mark.asyncio
async def test_proxy_no_auth(client: AsyncClient):
    response = await client.post(
        "/api/v1/proxy/",
        json={"prompt": "hello"}
    )
    assert response.status_code == 401

@pytest.mark.asyncio
async def test_proxy_invalid_auth(client: AsyncClient):
    response = await client.post(
        "/api/v1/proxy/",
        headers={"X-API-Key": "invalid-key"},
        json={"prompt": "hello"}
    )
    assert response.status_code == 401

@pytest.mark.asyncio
async def test_proxy_success(client: AsyncClient):
    # Create app to get key
    create_res = await client.post(
        "/api/v1/apps/",
        json={"name": "proxy-test-app"}
    )
    api_key = create_res.json()["api_key"]

    # Mock the HTTP call to security agent
    # We patch the AsyncClient class used in the proxy module, NOT the global one
    # to avoid affecting the test client itself.
    with patch("app.api.v1.endpoints.proxy.httpx.AsyncClient") as MockAsyncClient:
        # Setup the mock client instance that the context manager will yield
        mock_client_instance = AsyncMock()
        MockAsyncClient.return_value.__aenter__.return_value = mock_client_instance
        
        # Setup the response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "input": {"prompt": "hello world"},
            "security_score": 0.1,
            "is_blocked": False,
            "block_reason": None
        }
        mock_client_instance.post.return_value = mock_response
        
        # Call proxy
        response = await client.post(
            "/api/v1/proxy/",
            headers={"X-API-Key": api_key},
            json={"prompt": "hello world"}
        )
    assert response.status_code == 200
    data = response.json()
    assert data["app"] == "proxy-test-app"
    assert data["received_body"]["prompt"] == "hello world"
