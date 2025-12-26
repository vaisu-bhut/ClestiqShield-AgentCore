from fastapi import APIRouter, Request, HTTPException, status, Response
import httpx
import structlog
from app.core.config import get_settings
from jose import jwt, JWTError
from app.main import rate_limiter

router = APIRouter()
logger = structlog.get_logger()
settings = get_settings()

EAGLE_EYE_URL = "http://eagle-eye:8003"
APP_CREATION_LIMIT = 2
APP_CREATION_WINDOW = 600  # 10 mins
KEY_CREATION_LIMIT = 4
KEY_CREATION_WINDOW = 600  # 10 mins


def get_user_id_from_token(auth_header: str) -> str | None:
    if not auth_header or not auth_header.startswith("Bearer "):
        return None
    token = auth_header.split(" ")[1]
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        return payload.get("sub")
    except JWTError:
        return None


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
    # --- RATE LIMIT CHECK (Resource Creation) ---
    if request.method == "POST":
        user_id = get_user_id_from_token(request.headers.get("Authorization"))

        if user_id:
            # Check App Creation: POST /api/v1/apps (or just /apps if mounted there)
            # The path arg here comes from mount, so if mounted at /api/v1/apps, path might be empty or "/"
            # If mounted at /api/v1, path might be "apps"
            # Let's inspect the full URL path to be safe, or relying on the fact that this router handles specific mounts.

            full_path = request.url.path

            # 1. App Creation
            # Path ends with /apps or /apps/
            if full_path.endswith("/apps") or full_path.endswith("/apps/"):
                limit_key = f"rate:apps_created:{user_id}"
                allowed = await rate_limiter.check_limit(
                    limit_key, APP_CREATION_LIMIT, APP_CREATION_WINDOW
                )
                if not allowed:
                    logger.warning("App creation limit exceeded", user_id=user_id)
                    raise HTTPException(
                        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                        detail="App creation limit exceeded (2 apps / 10 mins)",
                    )

            # 2. Key Creation
            # Path matches .../apps/{app_id}/keys
            if (
                "/keys" in full_path and not "/keys/" in full_path
            ):  # simplistic check for collection POST
                # Better check: split by /
                parts = full_path.split("/")
                if parts[-1] == "keys" and parts[-3] == "apps":
                    limit_key = f"rate:keys_created:{user_id}"
                    allowed = await rate_limiter.check_limit(
                        limit_key, KEY_CREATION_LIMIT, KEY_CREATION_WINDOW
                    )
                    if not allowed:
                        logger.warning("Key creation limit exceeded", user_id=user_id)
                        raise HTTPException(
                            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                            detail="API Key creation limit exceeded (4 keys / 10 mins)",
                        )

    return await _proxy_request(request, request.url.path.replace("/api/v1", ""))
