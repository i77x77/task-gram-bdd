from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

Priority = Literal["low", "normal", "high", "urgent"]


# ---------- Ingest: контракт с Telegram-ботом ----------

class TgAuthor(BaseModel):
    id: int
    username: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    full_name: str | None = None
    language_code: str | None = None
    is_premium: bool = False


class TgChat(BaseModel):
    id: int
    type: str
    title: str | None = None


class TgEntities(BaseModel):
    hashtags: list[str] = []
    mentions: list[str] = []
    links: list[str] = []
    commands: list[str] = []


class TgAttachment(BaseModel):
    # location (latitude, longitude) и contact (phone_number, name) уходят в extra
    model_config = ConfigDict(extra="allow")

    type: str
    file_id: str | None = None
    file_unique_id: str | None = None
    file_name: str | None = None
    mime_type: str | None = None
    file_size: int | None = None


class TgReplyTo(BaseModel):
    message_id: int
    text: str | None = None


class TelegramTaskIn(BaseModel):
    text: str = ""
    sent_at: datetime
    sent_at_unix: int | None = None
    author: TgAuthor
    chat: TgChat
    message_id: int
    entities: TgEntities = TgEntities()
    attachments: list[TgAttachment] = []
    forwarded_from: dict | None = None
    reply_to: TgReplyTo | None = None
    edited: bool = False


class IngestResult(BaseModel):
    task_id: int
    status: Literal["created", "updated", "duplicate"]


# ---------- Задачи ----------

class AuthorOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str | None
    full_name: str | None


class AttachmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    type: str
    file_id: str | None
    file_name: str | None
    mime_type: str | None
    file_size: int | None
    extra: dict | None


class TaskOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: str
    column_id: int
    position: int
    priority: Priority
    due_at: datetime | None
    source: str
    chat_id: int | None
    message_id: int | None
    author: AuthorOut | None
    sent_at: datetime | None
    edited: bool
    tags: list[str]
    entities: dict | None
    attachments: list[AttachmentOut]
    created_at: datetime
    updated_at: datetime

    @field_validator("tags", mode="before")
    @classmethod
    def _tag_names(cls, v):
        return [getattr(t, "name", t) for t in v]


class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = ""
    column_id: int | None = None  # по умолчанию — первая колонка
    priority: Priority = "normal"
    due_at: datetime | None = None
    tags: list[str] = []


class TaskUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    priority: Priority | None = None
    due_at: datetime | None = None
    tags: list[str] | None = None


class TaskMove(BaseModel):
    column_id: int
    position: int = Field(default=0, ge=0, description="Индекс в целевой колонке (0 = сверху)")


class TaskList(BaseModel):
    items: list[TaskOut]
    total: int


# ---------- Колонки / доска ----------

class ColumnCreate(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    position: int | None = Field(default=None, ge=0)


class ColumnUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=64)
    position: int | None = Field(default=None, ge=0)


class ColumnOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    position: int


class BoardColumnOut(ColumnOut):
    tasks: list[TaskOut]


class BoardOut(BaseModel):
    columns: list[BoardColumnOut]


class TagOut(BaseModel):
    name: str
    count: int
