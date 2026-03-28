import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

"""
Two-layer auth:
1. API key (X-API-Key header) — required for all endpoints, same as before
2. JWT bearer token — for user-specific endpoints (favorites, analytics, preferences)
"""
import os
from datetime import datetime, timedelta, timezone

from fastapi import Security, Depends, HTTPException, status
from fastapi.security import APIKeyHeader, OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from dotenv import load_dotenv
from sqlalchemy.orm import Session

from database import get_db

load_dotenv()

# ── API key (existing, unchanged) ─────────────────────────────────────────────
_API_KEY       = os.getenv("API_KEY", "khmer-plate-secret-2025-itc-ams")
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

def require_api_key(key: str = Security(api_key_header)) -> str:
    if key != _API_KEY:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid or missing API key. Pass your key in the 'X-API-Key' header.",
        )
    return key


# ── JWT (new) ──────────────────────────────────────────────────────────────────
SECRET_KEY   = os.getenv("JWT_SECRET", "change-me-in-production-jwt-secret-khmerplate")
ALGORITHM    = "HS256"
TOKEN_EXPIRE = int(os.getenv("TOKEN_EXPIRE_MINUTES", "1440"))  # 24 h

pwd_ctx      = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/login", auto_error=False)


def hash_password(plain: str) -> str:
    return pwd_ctx.hash(plain)

def verify_password(plain: str, hashed: str) -> bool:
    return pwd_ctx.verify(plain, hashed)

def create_access_token(user_id: int, username: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=TOKEN_EXPIRE)
    payload = {"sub": str(user_id), "username": username, "exp": expire}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def get_current_user_optional(token: str = Depends(oauth2_scheme)):
    """Returns (user_id, username) if a valid JWT is present, else None."""
    if not token:
        return None
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id  = int(payload.get("sub"))
        username = payload.get("username")
        return {"user_id": user_id, "username": username}
    except (JWTError, ValueError, TypeError):
        return None


def require_current_user(token: str = Depends(oauth2_scheme)):
    """Raises 401 if no valid JWT."""
    user = get_current_user_optional(token)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Please log in to access this endpoint.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user
