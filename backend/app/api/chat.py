import time

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.call import participants
from app.database import get_db
from app.models import ChatMessage
from app.schemas import ChatMessageCreate, ChatMessageOut, Heartbeat, OnlineUser

router = APIRouter(prefix="/chat", tags=["chat"])

ONLINE_TTL = 30  # секунд без heartbeat — считаем, что пользователь ушёл
GUEST = "Гость"

# Присутствие живёт в памяти процесса: при перезапуске бэкенда клиенты за ≤10 с отметятся заново.
_presence: dict[str, tuple[str, float]] = {}


def _online() -> list[OnlineUser]:
    now = time.monotonic()
    for cid in [c for c, (_, seen) in _presence.items() if now - seen > ONLINE_TTL]:
        del _presence[cid]
    in_call = {p[2] for p in participants.values()}
    users = sorted(_presence.items(), key=lambda kv: kv[1][0].casefold())
    return [OnlineUser(client_id=cid, name=name, in_call=cid in in_call) for cid, (name, _) in users]


@router.get("/messages", response_model=list[ChatMessageOut])
def list_messages(
    after_id: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    """Без after_id — последние `limit` сообщений; с after_id — только новые."""
    if after_id:
        stmt = select(ChatMessage).where(ChatMessage.id > after_id).order_by(ChatMessage.id).limit(limit)
        return db.scalars(stmt).all()
    rows = db.scalars(select(ChatMessage).order_by(ChatMessage.id.desc()).limit(limit)).all()
    return rows[::-1]


@router.post("/messages", response_model=ChatMessageOut, status_code=status.HTTP_201_CREATED)
def send_message(body: ChatMessageCreate, db: Session = Depends(get_db)):
    name = body.author_name.strip() or GUEST
    msg = ChatMessage(client_id=body.client_id, author_name=name, text=body.text.strip())
    db.add(msg)
    db.commit()
    _presence[body.client_id] = (name, time.monotonic())
    return msg


@router.post("/heartbeat", response_model=list[OnlineUser])
def heartbeat(body: Heartbeat):
    """Клиент отмечается раз в несколько секунд; в ответ — кто сейчас онлайн."""
    _presence[body.client_id] = (body.name.strip() or GUEST, time.monotonic())
    return _online()
