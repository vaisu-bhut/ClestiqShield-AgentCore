from fastapi import APIRouter, Request, HTTPException, status, Response
import httpx
import structlog
from app.core.config import get_settings
from typing import Any

router = APIRouter()
logger = structlog.get_logger()
settings = get_settings()

EAGLE_EYE_URL = "http://eagle-eye:8003"


async def _proxy_request(request: Request, path: str):
    method = request.method
    url = f"{EAGLE_EYE_URL}{path}"

    # Forward headers, excluding host
    headers = dict(request.headers)
    headers.pop("host", None)
    headers.pop("content-length", None)  # Let httpx handle this

    # Get body
    body = await request.body()

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.request(
                method, url, headers=headers, content=body, params=request.query_params
            )

            # Proxy the response back
            return Response(
                content=response.content,
                status_code=response.status_code,
                headers=dict(response.headers),
            )
    except httpx.RequestError as exc:
        logger.error(f"Error proxying to EagleEye: {exc}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service unavailable",
        )
    except Exception as exc:
        logger.error(f"Unexpected error proxying to EagleEye: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unexpected Gateway Error",
        )


@router.api_route(
    "/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"]
)
async def proxy_eagle_eye(request: Request, path: str):
    return await _proxy_request(request, request.url.path.replace("/api/v1", ""))
