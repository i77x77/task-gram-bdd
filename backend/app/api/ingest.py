from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import IngestResult, TelegramTaskIn
from app.security import require_ingest_key
from app.services.ingest import ingest_telegram_task

router = APIRouter(prefix="/ingest", tags=["ingest"], dependencies=[Depends(require_ingest_key)])


@router.post("/telegram", response_model=IngestResult)
def ingest_telegram(payload: TelegramTaskIn, response: Response, db: Session = Depends(get_db)):
    """Приёмник JSON от Telegram-бота. Идемпотентен по (chat.id, message_id)."""
    result = ingest_telegram_task(db, payload)
    response.status_code = 201 if result.status == "created" else 200
    return result
