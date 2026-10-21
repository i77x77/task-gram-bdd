"""Бизнес-логика задач и доски. Роутеры тонкие, вся работа с БД здесь."""
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models import BoardColumn, Tag, Task


class NotFound(Exception):
    pass


class Conflict(Exception):
    pass


TASK_LOAD = (
    selectinload(Task.tags),
    selectinload(Task.attachments),
    selectinload(Task.author),
)


def seed_columns(db: Session, names: tuple[str, ...]) -> None:
    if db.scalar(select(func.count(BoardColumn.id))):
        return
    db.add_all(BoardColumn(name=n, position=i) for i, n in enumerate(names))
    db.commit()


def get_task(db: Session, task_id: int) -> Task:
    task = db.scalar(select(Task).where(Task.id == task_id).options(*TASK_LOAD))
    if task is None:
        raise NotFound(f"task {task_id}")
    return task


def get_column(db: Session, column_id: int) -> BoardColumn:
    col = db.get(BoardColumn, column_id)
    if col is None:
        raise NotFound(f"column {column_id}")
    return col


def default_column(db: Session) -> BoardColumn:
    col = db.scalar(select(BoardColumn).order_by(BoardColumn.position, BoardColumn.id).limit(1))
    if col is None:
        raise NotFound("no columns on the board")
    return col


def normalize_tag(raw: str) -> str:
    return raw.strip().lstrip("#").strip().lower()


def resolve_tags(db: Session, names: list[str]) -> list[Tag]:
    clean = list(dict.fromkeys(n for n in map(normalize_tag, names) if n))
    if not clean:
        return []
    existing = {t.name: t for t in db.scalars(select(Tag).where(Tag.name.in_(clean)))}
    tags = []
    for name in clean:
        tag = existing.get(name)
        if tag is None:
            tag = Tag(name=name)
            db.add(tag)
        tags.append(tag)
    return tags


def next_position(db: Session, column_id: int) -> int:
    top = db.scalar(select(func.max(Task.position)).where(Task.column_id == column_id))
    return 0 if top is None else top + 1


def _renumber(db: Session, column_id: int, exclude_id: int | None = None) -> list[Task]:
    tasks = list(
        db.scalars(
            select(Task)
            .where(Task.column_id == column_id, Task.id != (exclude_id or -1))
            .order_by(Task.position, Task.id)
        )
    )
    for i, t in enumerate(tasks):
        t.position = i
    return tasks


def move_task(db: Session, task: Task, column_id: int, position: int) -> Task:
    get_column(db, column_id)
    old_column_id = task.column_id
    siblings = _renumber(db, column_id, exclude_id=task.id)
    position = min(position, len(siblings))
    siblings.insert(position, task)
    task.column_id = column_id
    for i, t in enumerate(siblings):
        t.position = i
    db.flush()
    if old_column_id != column_id:
        _renumber(db, old_column_id)
    db.commit()
    return get_task(db, task.id)


def reorder_columns(db: Session, column: BoardColumn, position: int) -> None:
    cols = list(db.scalars(select(BoardColumn).where(BoardColumn.id != column.id).order_by(BoardColumn.position, BoardColumn.id)))
    cols.insert(min(position, len(cols)), column)
    for i, c in enumerate(cols):
        c.position = i
