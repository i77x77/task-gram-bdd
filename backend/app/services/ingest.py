from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Attachment, Chat, Task, User
from app.schemas import IngestResult, TelegramTaskIn, TgAttachment
from app.services import tasks as svc

TITLE_MAX = 200


def split_text(text: str, attachments: list[TgAttachment]) -> tuple[str, str]:
    """Первая непустая строка — заголовок, остальное — описание."""
    text = text.strip()
    if text:
        first, _, rest = text.partition("\n")
        first = first.strip()
        if len(first) > TITLE_MAX:
            return first[: TITLE_MAX - 1] + "…", text
        return first, rest.strip()
    for a in attachments:
        if a.file_name:
            return f"[{a.type}] {a.file_name}", ""
    if attachments:
        return f"[{attachments[0].type}]", ""
    return "(без текста)", ""


def _upsert_user_and_chat(db: Session, payload: TelegramTaskIn) -> None:
    a = payload.author
    user = db.get(User, a.id)
    if user is None:
        db.add(User(**a.model_dump()))
    else:
        for k, v in a.model_dump().items():
            setattr(user, k, v)

    c = payload.chat
    chat = db.get(Chat, c.id)
    if chat is None:
        db.add(Chat(**c.model_dump()))
    else:
        chat.type, chat.title = c.type, c.title


def _make_attachments(items: list[TgAttachment]) -> list[Attachment]:
    known = {"type", "file_id", "file_unique_id", "file_name", "mime_type", "file_size"}
    result = []
    for item in items:
        data = item.model_dump()
        extra = {k: v for k, v in data.items() if k not in known} or None
        result.append(Attachment(**{k: data[k] for k in known & data.keys()}, extra=extra))
    return result


def ingest_telegram_task(db: Session, payload: TelegramTaskIn) -> IngestResult:
    existing = db.scalar(
        select(Task)
        .where(
            Task.chat_id == payload.chat.id,
            Task.message_id == payload.message_id,
            Task.part == payload.part,
        )
        .options(*svc.TASK_LOAD)
    )

    # Повторная доставка того же сообщения без edited — ничего не делаем
    if existing is not None and not payload.edited:
        return IngestResult(task_id=existing.id, status="duplicate")

    _upsert_user_and_chat(db, payload)
    if payload.title:
        title, description = payload.title, payload.description or ""
    else:
        title, description = split_text(payload.text, payload.attachments)
    tags = svc.resolve_tags(db, payload.entities.hashtags)
    entities = payload.entities.model_dump()

    if existing is not None:
        # Правка сообщения: обновляем содержимое, колонку и позицию на доске не трогаем
        existing.title, existing.description = title, description
        if payload.priority:
            existing.priority = payload.priority
        existing.entities = entities
        existing.tags = tags
        existing.attachments = _make_attachments(payload.attachments)
        existing.forwarded_from = payload.forwarded_from
        existing.reply_to = payload.reply_to.model_dump() if payload.reply_to else None
        existing.edited = True
        db.commit()
        return IngestResult(task_id=existing.id, status="updated")

    column = svc.default_column(db)
    task = Task(
        title=title,
        description=description,
        column_id=column.id,
        position=svc.next_position(db, column.id),
        source="telegram",
        chat_id=payload.chat.id,
        message_id=payload.message_id,
        part=payload.part,
        priority=payload.priority or "normal",
        author_id=payload.author.id,
        sent_at=payload.sent_at,
        edited=payload.edited,
        entities=entities,
        forwarded_from=payload.forwarded_from,
        reply_to=payload.reply_to.model_dump() if payload.reply_to else None,
        tags=tags,
        attachments=_make_attachments(payload.attachments),
    )
    db.add(task)
    db.commit()
    return IngestResult(task_id=task.id, status="created")
