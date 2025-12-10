from passlib.context import CryptContext
import secrets
import hashlib
from datetime import datetime, timedelta
from typing import Optional
from jose import jwt
from app.core.config import get_settings

settings = get_settings()
# Switch to Argon2 to avoid bcrypt compatibility issues
pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(
        to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM
    )
    return encoded_jwt


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def generate_api_key(prefix: str = "clq_") -> str:
    """Generate a secure random API key."""
    return f"{prefix}{secrets.token_urlsafe(32)}"


def hash_api_key(api_key: str) -> str:
    """Hash the API key for storage."""
    # Using SHA256 for API keys is standard and fast enough
    return hashlib.sha256(api_key.encode()).hexdigest()


def verify_api_key(plain_api_key: str, hashed_api_key: str) -> bool:
    """Verify an API key against its hash."""
    return hash_api_key(plain_api_key) == hashed_api_key


def mask_api_key(api_key: str) -> str:
    """Return a masked version of the API key (prefix...suffix)."""
    if len(api_key) < 10:
        return api_key
    return f"{api_key[:4]}...{api_key[-4:]}"
