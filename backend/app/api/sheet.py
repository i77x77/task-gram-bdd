from fastapi import APIRouter, HTTPException

from app.config import get_settings
from app.services import sheet

router = APIRouter(prefix="/sheet", tags=["sheet"])


@router.get("")
def status():
    return {"enabled": bool(get_settings().sheet_url)}


@router.post("/sync")
def sync():
    """Ручная синхронизация с Google-таблицей: создаёт задачи для новых строк и переносит прошедшие в Done."""
    if not get_settings().sheet_url:
        raise HTTPException(404, "SHEET_URL не задан")
    try:
        created, archived = sheet.sync_once()
    except Exception as e:  # noqa: BLE001 — показываем причину пользователю
        raise HTTPException(502, f"Не удалось прочитать таблицу: {e}") from e
    return {"created": created, "archived": archived}
