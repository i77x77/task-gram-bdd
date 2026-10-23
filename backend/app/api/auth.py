from fastapi import APIRouter, Depends

from app.security import require_app_password

router = APIRouter(prefix="/auth", tags=["auth"], dependencies=[Depends(require_app_password)])


@router.get("/check")
def check():
    """200, если пароль верный (или не задан)."""
    return {"ok": True}
