from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Tag, Task, task_tags
from app.schemas import Priority, TaskCreate, TaskList, TaskMove, TaskOut, TaskUpdate
from app.services import tasks as svc

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.get("", response_model=TaskList)
def list_tasks(
    column_id: int | None = None,
    tag: str | None = None,
    author_id: int | None = None,
    chat_id: int | None = None,
    priority: Priority | None = None,
    q: str | None = Query(default=None, description="Поиск по заголовку и описанию"),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    stmt = select(Task)
    if column_id is not None:
        stmt = stmt.where(Task.column_id == column_id)
    if author_id is not None:
        stmt = stmt.where(Task.author_id == author_id)
    if chat_id is not None:
        stmt = stmt.where(Task.chat_id == chat_id)
    if priority is not None:
        stmt = stmt.where(Task.priority == priority)
    if tag:
        stmt = stmt.where(
            Task.id.in_(
                select(task_tags.c.task_id).join(Tag, Tag.id == task_tags.c.tag_id).where(Tag.name == svc.normalize_tag(tag))
            )
        )
    if q:
        like = f"%{q}%"
        stmt = stmt.where(or_(Task.title.ilike(like), Task.description.ilike(like)))

    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    items = db.scalars(
        stmt.order_by(Task.column_id, Task.position, Task.id).limit(limit).offset(offset).options(*svc.TASK_LOAD)
    ).all()
    return TaskList(items=items, total=total)


@router.post("", response_model=TaskOut, status_code=status.HTTP_201_CREATED)
def create_task(body: TaskCreate, db: Session = Depends(get_db)):
    column = svc.get_column(db, body.column_id) if body.column_id else svc.default_column(db)
    task = Task(
        title=body.title.strip(),
        description=body.description,
        column_id=column.id,
        position=svc.next_position(db, column.id),
        priority=body.priority,
        due_at=body.due_at,
        source="manual",
        tags=svc.resolve_tags(db, body.tags),
    )
    db.add(task)
    db.commit()
    return svc.get_task(db, task.id)


@router.get("/{task_id}", response_model=TaskOut)
def read_task(task_id: int, db: Session = Depends(get_db)):
    return svc.get_task(db, task_id)


@router.patch("/{task_id}", response_model=TaskOut)
def update_task(task_id: int, body: TaskUpdate, db: Session = Depends(get_db)):
    task = svc.get_task(db, task_id)
    data = body.model_dump(exclude_unset=True)
    tags = data.pop("tags", None)
    for key, value in data.items():
        if key in ("title", "priority") and value is None:
            continue
        setattr(task, key, value)
    if tags is not None:
        task.tags = svc.resolve_tags(db, tags)
    db.commit()
    return svc.get_task(db, task_id)


@router.post("/{task_id}/move", response_model=TaskOut)
def move_task(task_id: int, body: TaskMove, db: Session = Depends(get_db)):
    """Drag-and-drop: перенос в колонку column_id на позицию position."""
    task = svc.get_task(db, task_id)
    return svc.move_task(db, task, body.column_id, body.position)


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(task_id: int, db: Session = Depends(get_db)):
    task = svc.get_task(db, task_id)
    column_id = task.column_id
    db.delete(task)
    db.flush()
    svc._renumber(db, column_id)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
