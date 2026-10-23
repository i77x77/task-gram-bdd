from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.models import Board, BoardColumn, Tag, Task, task_tags
from app.schemas import (
    BoardInfo,
    BoardOut,
    ColumnCreate,
    ColumnOut,
    ColumnUpdate,
    TagOut,
)
from app.services import tasks as svc

router = APIRouter(tags=["board"])


@router.get("/boards", response_model=list[BoardInfo])
def list_boards(db: Session = Depends(get_db)):
    return db.scalars(select(Board).order_by(Board.position, Board.id)).all()


@router.get("/board", response_model=BoardOut)
def get_board(
    board_id: int | None = None,
    tag: str | None = None,
    author_id: int | None = None,
    q: str | None = Query(default=None, description="Поиск по заголовку и описанию"),
    db: Session = Depends(get_db),
):
    """Вся канбан-доска одним запросом: колонки с задачами в порядке отображения."""
    board = svc.get_board(db, board_id)
    columns = db.scalars(
        select(BoardColumn).where(BoardColumn.board_id == board.id).order_by(BoardColumn.position, BoardColumn.id)
    ).all()

    stmt = select(Task).where(Task.column_id.in_([c.id for c in columns])).order_by(Task.position, Task.id).options(*svc.TASK_LOAD)
    if author_id is not None:
        stmt = stmt.where(Task.author_id == author_id)
    if q:
        stmt = stmt.where(Task.title.ilike(f"%{q}%") | Task.description.ilike(f"%{q}%"))
    if tag:
        stmt = stmt.where(
            Task.id.in_(
                select(task_tags.c.task_id).join(Tag, Tag.id == task_tags.c.tag_id).where(Tag.name == svc.normalize_tag(tag))
            )
        )
    by_column: dict[int, list[Task]] = {c.id: [] for c in columns}
    for task in db.scalars(stmt):
        by_column[task.column_id].append(task)

    return BoardOut(
        id=board.id,
        name=board.name,
        columns=[
            {"id": c.id, "name": c.name, "position": c.position, "tasks": by_column[c.id]} for c in columns
        ]
    )


@router.get("/columns", response_model=list[ColumnOut])
def list_columns(board_id: int | None = None, db: Session = Depends(get_db)):
    board = svc.get_board(db, board_id)
    return db.scalars(
        select(BoardColumn).where(BoardColumn.board_id == board.id).order_by(BoardColumn.position, BoardColumn.id)
    ).all()


@router.post("/columns", response_model=ColumnOut, status_code=status.HTTP_201_CREATED)
def create_column(body: ColumnCreate, board_id: int | None = None, db: Session = Depends(get_db)):
    board = svc.get_board(db, board_id)
    name = body.name.strip()
    if db.scalar(select(BoardColumn.id).where(BoardColumn.board_id == board.id, BoardColumn.name == name)):
        raise svc.Conflict(f"column '{name}' already exists")
    column = BoardColumn(board_id=board.id, name=name, position=10**9)
    db.add(column)
    db.flush()
    count = db.scalar(select(func.count(BoardColumn.id)).where(BoardColumn.board_id == board.id))
    svc.reorder_columns(db, column, body.position if body.position is not None else count)
    db.commit()
    return column


@router.patch("/columns/{column_id}", response_model=ColumnOut)
def update_column(column_id: int, body: ColumnUpdate, db: Session = Depends(get_db)):
    column = svc.get_column(db, column_id)
    if body.name is not None:
        name = body.name.strip()
        clash = db.scalar(select(BoardColumn.id).where(
                BoardColumn.board_id == column.board_id, BoardColumn.name == name, BoardColumn.id != column_id
            ))
        if clash:
            raise svc.Conflict(f"column '{name}' already exists")
        column.name = name
    if body.position is not None:
        svc.reorder_columns(db, column, body.position)
    db.commit()
    return column


@router.delete("/columns/{column_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_column(column_id: int, move_to: int | None = None, db: Session = Depends(get_db)):
    """Колонку с задачами нельзя удалить без `move_to` — id колонки, куда перенести задачи."""
    column = svc.get_column(db, column_id)
    tasks = db.scalars(select(Task).where(Task.column_id == column_id).order_by(Task.position)).all()
    if tasks:
        if move_to is None or move_to == column_id:
            raise svc.Conflict("column is not empty: pass move_to=<column_id>")
        target = svc.get_column(db, move_to)
        start = svc.next_position(db, target.id)
        for i, t in enumerate(tasks):
            t.column_id, t.position = target.id, start + i
        db.flush()
    elif db.scalar(select(func.count(BoardColumn.id)).where(BoardColumn.board_id == column.board_id)) == 1:
        raise svc.Conflict("cannot delete the last column")
    db.delete(column)
    db.flush()
    siblings = select(BoardColumn).where(BoardColumn.board_id == column.board_id)
    for i, c in enumerate(db.scalars(siblings.order_by(BoardColumn.position, BoardColumn.id))):
        c.position = i
    db.commit()


@router.get("/tags", response_model=list[TagOut])
def list_tags(db: Session = Depends(get_db)):
    rows = db.execute(
        select(Tag.name, func.count(task_tags.c.task_id))
        .outerjoin(task_tags, task_tags.c.tag_id == Tag.id)
        .group_by(Tag.id)
        .order_by(Tag.name)
    )
    return [TagOut(name=n, count=c) for n, c in rows]
