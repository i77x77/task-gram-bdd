import secrets

from fastapi import Header, HTTPException, status

from app.config import get_settings


def require_ingest_key(authorization: str | None = Header(default=None)) -> None:
    key = get_settings().ingest_api_key
    if not key:
        return
    scheme, _, token = (authorization or "").partition(" ")
    if scheme.lower() != "bearer" or not secrets.compare_digest(token, key):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid API key", headers={"WWW-Authenticate": "Bearer"})
