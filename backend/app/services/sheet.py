"""Импорт презентаций из Google-таблицы: 1-й столбец — название, 2-й — дата выступления."""
import asyncio
import csv
import hashlib
import io
import logging
import re
import urllib.request
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import SessionLocal
from app.models import SheetRow, Task
from app.services import tasks as svc

log = logging.getLogger("sheet")

DATE_RE = re.compile(r"(\d{1,4})[./-](\d{1,2})(?:[./-](\d{1,4}))?(?:[ T,]+(\d{1,2})[:.](\d{2}))?")
SHEET_ID_RE = re.compile(r"/spreadsheets/d/([\w-]+)")
GID_RE = re.compile(r"[#&?]gid=(\d+)")


def csv_url(url: str) -> str:
    """Ссылка на таблицу (…/edit#gid=0) -> ссылка на CSV-экспорт; прямую ссылку на экспорт возвращаем как есть."""
    m = SHEET_ID_RE.search(url)
    if not m or "/export" in url or "/pub" in url:
        return url
    gid = GID_RE.search(url)
    return f"https://docs.google.com/spreadsheets/d/{m.group(1)}/export?format=csv&gid={gid.group(1) if gid else 0}"


def parse_date(raw: str) -> datetime | None:
    """dd.mm.yyyy / dd/mm/yyyy / yyyy-mm-dd / dd.mm (год по умолчанию из настроек), опционально с временем.
    Только дата -> 12:00 UTC (не уезжает на соседний день)."""
    m = DATE_RE.search(raw)
    if not m:
        return None
    a, b = int(m.group(1)), int(m.group(2))
    if m.group(3) is None:
        y, mo, d = get_settings().sheet_default_year, b, a
    else:
        c = int(m.group(3))
        y, mo, d = (a, b, c) if len(m.group(1)) == 4 else (c, b, a)
    if y < 100:
        y += 2000
    hh, mm = (int(m.group(4)), int(m.group(5))) if m.group(4) else (12, 0)
    try:
        return datetime(y, mo, d, hh, mm, tzinfo=timezone.utc)
    except ValueError:
        return None


def parse_rows(text: str) -> list[tuple[str, str, datetime | None]]:
    rows = list(csv.reader(io.StringIO(text)))
    out = []
    for i, row in enumerate(rows):
        title = row[0].strip() if row else ""
        raw = row[1].strip() if len(row) > 1 else ""
        due = parse_date(raw)
        if not title or (i == 0 and due is None):  # пустая строка или шапка таблицы
            continue
        out.append((title[:200], raw, due))
    return out


def row_key(title: str, raw_date: str) -> str:
    return hashlib.sha1(f"{title.casefold()}|{raw_date}".encode()).hexdigest()


def import_rows(db: Session, rows: list[tuple[str, str, datetime | None]]) -> int:
    settings = get_settings()
    board = svc.get_board_by_name(db, settings.sheet_board)
    column = svc.get_or_create_column(db, settings.sheet_column, board.id)
    known = {k for (k,) in db.query(SheetRow.key)}
    created = 0
    for title, raw, due in rows:
        key = row_key(title, raw)
        if key in known:
            if due:  # раньше дата не распозналась (например, 16.11 без года) — дозаполняем срок
                row = db.get(SheetRow, key)
                task = row and row.task_id and db.get(Task, row.task_id)
                if task and task.source == "sheet" and task.due_at is None:
                    task.due_at = due
                    task.description = ""
            continue
        known.add(key)
        task = Task(
            title=title,
            description="" if due else f"Дата выступления: {raw}" if raw else "",
            column_id=column.id,
            position=svc.next_position(db, column.id),
            due_at=due,
            source="sheet",
            author_name="Google Sheets",
        )
        db.add(task)
        db.flush()
        db.add(SheetRow(key=key, task_id=task.id))
        created += 1
    db.commit()
    return created


def archive_past(db: Session) -> int:
    """Задачи из таблицы, которые ещё лежат в To Do и у которых дата прошла, переносит в Done.
    Задачи, которые пользователь уже сам переложил в другую колонку, не трогаем."""
    settings = get_settings()
    board = svc.get_board_by_name(db, settings.sheet_board)
    todo = svc.get_or_create_column(db, settings.sheet_column, board.id)
    done = svc.get_or_create_column(db, settings.sheet_done_column, board.id)
    past = db.scalars(
        select(Task)
        .where(Task.column_id == todo.id, Task.source == "sheet", Task.due_at.is_not(None), Task.due_at < datetime.now(timezone.utc))
        .order_by(Task.due_at)
    ).all()
    for t in past:
        t.column_id = done.id
        t.position = svc.next_position(db, done.id)
        db.flush()
    if past:
        svc._renumber(db, todo.id)
    db.commit()
    return len(past)


def _fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "taskgram"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        return resp.read().decode("utf-8-sig")


def sync_once() -> int:
    text = _fetch(csv_url(get_settings().sheet_url))
    if text.lstrip().lower().startswith(("<!doctype", "<html")):
        raise RuntimeError("таблица недоступна: откройте доступ «у кого есть ссылка — читатель»")
    with SessionLocal() as db:
        created = import_rows(db, parse_rows(text))
        archive_past(db)
        return created


async def sync_loop() -> None:
    settings = get_settings()
    while True:
        try:
            n = await asyncio.to_thread(sync_once)
            if n:
                log.info("sheet: создано задач: %d", n)
        except Exception as e:  # noqa: BLE001 — сеть/таблица не должны ронять сервер
            log.warning("sheet: %s", e)
        await asyncio.sleep(max(settings.sheet_poll_seconds, 10))
