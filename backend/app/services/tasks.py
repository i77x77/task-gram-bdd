"""Бизнес-логика задач и доски. Роутеры тонкие, вся работа с БД здесь."""
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models import Board, BoardColumn, Tag, Task


class NotFound(Exception):
    pass


class Conflict(Exception):
    pass


TASK_LOAD = (
    selectinload(Task.tags),
    selectinload(Task.attachments),
    selectinload(Task.author),
)


def seed_boards(db: Session, boards: tuple[str, ...], columns: tuple[str, ...]) -> None:
    """Гарантирует доски проектов и наличие стартовых колонок на каждой."""
    existing = {b.name for b in db.scalars(select(Board))}
    for name in boards:
        if name not in existing:
            db.add(Board(name=name, position=len(existing)))
            existing.add(name)
    db.flush()
    for board in db.scalars(select(Board)):
        have = {c.name.casefold() for c in db.scalars(select(BoardColumn).where(BoardColumn.board_id == board.id))}
        pos = len(have)
        for n in columns:  # недостающие стартовые колонки добавляются в конец
            if n.casefold() not in have:
                db.add(BoardColumn(board_id=board.id, name=n, position=pos))
                pos += 1
    db.commit()


def get_board(db: Session, board_id: int | None) -> Board:
    """Доска по id; без id — первая."""
    if board_id is None:
        board = db.scalar(select(Board).order_by(Board.position, Board.id).limit(1))
    else:
        board = db.get(Board, board_id)
    if board is None:
        raise NotFound(f"board {board_id}" if board_id is not None else "no boards")
    return board


def get_board_by_name(db: Session, name: str) -> Board:
    name = name.strip()
    board = next((b for b in db.scalars(select(Board)) if b.name.casefold() == name.casefold()), None)
    if board is None:
        raise NotFound(f"board {name}")
    return board


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


def get_or_create_column(db: Session, name: str, board_id: int) -> BoardColumn:
    """Колонка доски по имени (без учёта регистра); если такой нет — создаётся в конце доски."""
    name = name.strip()
    columns = db.scalars(select(BoardColumn).where(BoardColumn.board_id == board_id)).all()
    column = next((c for c in columns if c.name.casefold() == name.casefold()), None)  # lower() в SQLite не знает кириллицу
    if column is None:
        column = BoardColumn(board_id=board_id, name=name, position=len(columns))
        db.add(column)
        db.flush()
    return column


def default_column(db: Session, board_id: int) -> BoardColumn:
    col = db.scalar(
        select(BoardColumn).where(BoardColumn.board_id == board_id).order_by(BoardColumn.position, BoardColumn.id).limit(1)
    )
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
    cols = list(
        db.scalars(
            select(BoardColumn)
            .where(BoardColumn.board_id == column.board_id, BoardColumn.id != column.id)
            .order_by(BoardColumn.position, BoardColumn.id)
        )
    )
    cols.insert(min(position, len(cols)), column)
    for i, c in enumerate(cols):
        c.position = i
