from datetime import datetime, timezone

from sqlalchemy import JSON, BigInteger, ForeignKey, Index, String, Table, Column as SAColumn, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base, UTCDateTime


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


task_tags = Table(
    "task_tags",
    Base.metadata,
    SAColumn("task_id", ForeignKey("tasks.id", ondelete="CASCADE"), primary_key=True),
    SAColumn("tag_id", ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True),
)


class User(Base):
    """Telegram-пользователь; PK = Telegram ID (username может меняться)."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    username: Mapped[str | None] = mapped_column(String(64))
    first_name: Mapped[str | None] = mapped_column(String(128))
    last_name: Mapped[str | None] = mapped_column(String(128))
    full_name: Mapped[str | None] = mapped_column(String(256))
    language_code: Mapped[str | None] = mapped_column(String(16))
    is_premium: Mapped[bool] = mapped_column(default=False)


class Chat(Base):
    __tablename__ = "chats"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    type: Mapped[str] = mapped_column(String(16))
    title: Mapped[str | None] = mapped_column(String(256))


class BoardColumn(Base):
    __tablename__ = "board_columns"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(64), unique=True)
    position: Mapped[int] = mapped_column(default=0)

    tasks: Mapped[list["Task"]] = relationship(
        back_populates="column", order_by="Task.position", cascade="save-update"
    )


class Tag(Base):
    __tablename__ = "tags"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(64), unique=True)


class Task(Base):
    __tablename__ = "tasks"
    __table_args__ = (
        # Ключ идемпотентности для задач из Telegram; у ручных задач chat_id = NULL
        UniqueConstraint("chat_id", "message_id", "part", name="uq_task_chat_message_part"),
        Index("ix_tasks_column_position", "column_id", "position"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(default="")
    column_id: Mapped[int] = mapped_column(ForeignKey("board_columns.id", ondelete="RESTRICT"))
    position: Mapped[int] = mapped_column(default=0)
    priority: Mapped[str] = mapped_column(String(16), default="normal")
    due_at: Mapped[datetime | None] = mapped_column(UTCDateTime)

    source: Mapped[str] = mapped_column(String(16), default="manual")  # manual | telegram
    chat_id: Mapped[int | None] = mapped_column(ForeignKey("chats.id"))
    message_id: Mapped[int | None] = mapped_column(BigInteger)
    part: Mapped[int] = mapped_column(default=0)  # номер задачи внутри сообщения (одно сообщение -> несколько задач)
    author_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    author_name: Mapped[str | None] = mapped_column(String(100))  # имя автора ручной задачи
    sent_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    edited: Mapped[bool] = mapped_column(default=False)
    entities: Mapped[dict | None] = mapped_column(JSON)
    forwarded_from: Mapped[dict | None] = mapped_column(JSON)
    reply_to: Mapped[dict | None] = mapped_column(JSON)

    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, onupdate=utcnow)

    column: Mapped[BoardColumn] = relationship(back_populates="tasks")
    author: Mapped[User | None] = relationship()
    chat: Mapped[Chat | None] = relationship()
    tags: Mapped[list[Tag]] = relationship(secondary=task_tags, order_by="Tag.name")
    attachments: Mapped[list["Attachment"]] = relationship(
        back_populates="task", cascade="all, delete-orphan", order_by="Attachment.id"
    )


class Attachment(Base):
    __tablename__ = "attachments"

    id: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"), index=True)
    type: Mapped[str] = mapped_column(String(16))
    file_id: Mapped[str | None] = mapped_column(String(256))
    file_unique_id: Mapped[str | None] = mapped_column(String(128))
    file_name: Mapped[str | None] = mapped_column(String(256))
    mime_type: Mapped[str | None] = mapped_column(String(128))
    file_size: Mapped[int | None] = mapped_column(BigInteger)
    extra: Mapped[dict | None] = mapped_column(JSON)  # location / contact

    task: Mapped[Task] = relationship(back_populates="attachments")
