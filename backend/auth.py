import os
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import HTTPException, Request

JWT_ALGORITHM = "HS256"
_ADMIN_HASH = None


def _admin_hash() -> str:
    global _ADMIN_HASH
    if _ADMIN_HASH is None:
        pw = os.environ["ADMIN_PASSWORD"].encode("utf-8")
        _ADMIN_HASH = bcrypt.hashpw(pw, bcrypt.gensalt()).decode("utf-8")
    return _ADMIN_HASH


def verify_admin(username: str, password: str) -> bool:
    if username != os.environ["ADMIN_USERNAME"]:
        return False
    return bcrypt.checkpw(password.encode("utf-8"), _admin_hash().encode("utf-8"))


def create_access_token(username: str) -> str:
    payload = {
        "sub": username,
        "role": "admin",
        "type": "access",
        "exp": datetime.now(timezone.utc) + timedelta(hours=12),
    }
    return jwt.encode(payload, os.environ["JWT_SECRET"], algorithm=JWT_ALGORITHM)


async def require_admin(request: Request) -> str:
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")
    token = auth_header[7:]
    try:
        payload = jwt.decode(token, os.environ["JWT_SECRET"], algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Session expired, please log in again")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")
    if payload.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return payload["sub"]
