import pytest

from tests.conftest import AUTH, tg_payload


def ingest(client, **over):
    return client.post("/api/v1/ingest/telegram", json=tg_payload(**over), headers=AUTH)


def test_auth_required(client):
    assert client.post("/api/v1/ingest/telegram", json=tg_payload()).status_code == 401
    bad = client.post("/api/v1/ingest/telegram", json=tg_payload(), headers={"Authorization": "Bearer no"})
    assert bad.status_code == 401


def test_ingest_create_duplicate_edit(client):
    r = ingest(client)
    assert r.status_code == 201 and r.json()["status"] == "created"
    tid = r.json()["task_id"]

    r = ingest(client)
    assert r.status_code == 200 and r.json() == {"task_id": tid, "status": "duplicate"}

    client.post(f"/api/v1/tasks/{tid}/move", json={"column_id": 2, "position": 0})
    r = ingest(client, text="Купить кефир\nи хлеб #еда", edited=True,
               entities={"hashtags": ["#еда"], "mentions": [], "links": [], "commands": []})
    assert r.json() == {"task_id": tid, "status": "updated"}

    t = client.get(f"/api/v1/tasks/{tid}").json()
    assert t["title"] == "Купить кефир" and t["description"] == "и хлеб #еда"
    assert t["tags"] == ["еда"] and t["edited"] is True
    assert t["column_id"] == 2  # правка не сбрасывает колонку
    assert t["author"]["username"] == "art"
    assert t["sent_at"].startswith("2026-10-21T09:06:18")


def test_ingest_attachments_and_empty_text(client):
    atts = [{"type": "document", "file_id": "f", "file_unique_id": "u", "file_name": "spec.pdf",
             "mime_type": "application/pdf", "file_size": 10},
            {"type": "location", "latitude": 1.5, "longitude": 2.5}]
    tid = ingest(client, text="", attachments=atts, entities={}).json()["task_id"]
    t = client.get(f"/api/v1/tasks/{tid}").json()
    assert t["title"] == "[document] spec.pdf"
    assert t["attachments"][1]["extra"] == {"latitude": 1.5, "longitude": 2.5}


def test_board_and_move(client):
    ids = [ingest(client, message_id=i, text=f"t{i}").json()["task_id"] for i in range(1, 4)]
    board = client.get("/api/v1/board").json()
    assert [c["name"] for c in board["columns"]] == ["To Do", "In Progress", "Done", "Backlog"]
    assert [t["title"] for t in board["columns"][0]["tasks"]] == ["t1", "t2", "t3"]

    client.post(f"/api/v1/tasks/{ids[2]}/move", json={"column_id": 2, "position": 0})
    client.post(f"/api/v1/tasks/{ids[0]}/move", json={"column_id": 2, "position": 0})
    board = client.get("/api/v1/board").json()
    assert [t["title"] for t in board["columns"][0]["tasks"]] == ["t2"]
    assert [t["title"] for t in board["columns"][1]["tasks"]] == ["t1", "t3"]
    assert [t["position"] for t in board["columns"][1]["tasks"]] == [0, 1]

    # перестановка внутри колонки
    client.post(f"/api/v1/tasks/{ids[2]}/move", json={"column_id": 2, "position": 0})
    titles = [t["title"] for t in client.get("/api/v1/board").json()["columns"][1]["tasks"]]
    assert titles == ["t3", "t1"]
    assert client.post(f"/api/v1/tasks/{ids[0]}/move", json={"column_id": 99}).status_code == 404


def test_task_crud_and_filters(client):
    r = client.post("/api/v1/tasks", json={"title": "Ручная", "tags": ["#Work"], "priority": "high"})
    assert r.status_code == 201
    tid = r.json()["id"]
    ingest(client, text="из бота")

    assert client.get("/api/v1/tasks").json()["total"] == 2
    assert client.get("/api/v1/tasks?tag=work").json()["total"] == 1
    assert client.get("/api/v1/tasks?q=бота").json()["items"][0]["source"] == "telegram"
    assert client.get("/api/v1/board?tag=work").json()["columns"][0]["tasks"][0]["id"] == tid

    r = client.patch(f"/api/v1/tasks/{tid}", json={"title": "Новая", "tags": [], "due_at": "2026-12-01T10:00:00Z"})
    assert r.json()["title"] == "Новая" and r.json()["tags"] == [] and r.json()["due_at"].startswith("2026-12-01T10:00")
    assert client.delete(f"/api/v1/tasks/{tid}").status_code == 204
    assert client.get(f"/api/v1/tasks/{tid}").status_code == 404
    tags = client.get("/api/v1/tags").json()
    assert {"name": "дом", "count": 1} in tags


def test_columns(client):
    r = client.post("/api/v1/columns", json={"name": "Review", "position": 2})
    assert r.status_code == 201
    names = [c["name"] for c in client.get("/api/v1/columns").json()]
    assert names == ["To Do", "In Progress", "Review", "Done", "Backlog"]
    assert client.post("/api/v1/columns", json={"name": "Review"}).status_code == 409

    client.patch(f"/api/v1/columns/{r.json()['id']}", json={"position": 0})
    assert client.get("/api/v1/columns").json()[0]["name"] == "Review"

    ingest(client)  # в первую колонку (Review)
    first = client.get("/api/v1/columns").json()[0]["id"]
    assert client.delete(f"/api/v1/columns/{first}").status_code == 409
    assert client.delete(f"/api/v1/columns/{first}?move_to=2").status_code == 204
    board = client.get("/api/v1/board").json()
    assert [c["name"] for c in board["columns"]] == ["To Do", "In Progress", "Done", "Backlog"]
    assert len(board["columns"][1]["tasks"]) == 1


def test_ingest_multiple_parts_from_one_message(client):
    a = ingest(client, part=0, title="Купить молоко", description="2 литра", priority="high")
    b = ingest(client, part=1, title="Позвонить маме")
    assert a.status_code == b.status_code == 201
    assert a.json()["task_id"] != b.json()["task_id"]
    assert ingest(client, part=1, title="Позвонить маме").json()["status"] == "duplicate"

    t = client.get(f"/api/v1/tasks/{a.json()['task_id']}").json()
    assert (t["title"], t["description"], t["priority"]) == ("Купить молоко", "2 литра", "high")
    assert client.get(f"/api/v1/tasks/{b.json()['task_id']}").json()["priority"] == "normal"


def test_ingest_column_by_name_creates_missing(client):
    a = ingest(client, part=0, title="Идея", column="Backlog")
    b = ingest(client, part=1, title="Ещё идея", column="backlog")
    c = ingest(client, part=2, title="В работу", column="in progress")
    cols = {c["name"]: c["id"] for c in client.get("/api/v1/columns").json()}
    assert "Backlog" in cols and list(cols).count("Backlog") == 1
    for r, name in ((a, "Backlog"), (b, "Backlog"), (c, "In Progress")):
        assert client.get(f"/api/v1/tasks/{r.json()['task_id']}").json()["column_id"] == cols[name]


def test_boards_are_isolated(client):
    boards = client.get("/api/v1/boards").json()
    assert [b["name"] for b in boards] == ["ЕПУТС", "КИПАРИСС", "АИС ОМБУ", "Презентации"]
    kip = boards[1]["id"]

    board = client.get(f"/api/v1/board?board_id={kip}").json()
    assert board["name"] == "КИПАРИСС"
    assert [c["name"] for c in board["columns"]] == ["To Do", "In Progress", "Done", "Backlog"]

    r = client.post("/api/v1/tasks", json={"title": "в кипарисс", "board_id": kip})
    assert r.status_code == 201
    assert r.json()["column_id"] == board["columns"][0]["id"]
    assert client.get("/api/v1/board").json()["columns"][0]["tasks"] == []  # первая доска пуста

    # одинаковые имена колонок в разных досках допустимы
    assert client.post(f"/api/v1/columns?board_id={kip}", json={"name": "Review"}).status_code == 201
    assert client.post("/api/v1/columns", json={"name": "Review"}).status_code == 201
    assert client.get("/api/v1/board?board_id=999").status_code == 404


def test_ingest_to_board_by_name(client):
    r = ingest(client, title="Задача", board="аис омбу")
    assert r.status_code == 201
    board = client.get("/api/v1/board?board_id=3").json()
    assert [t["title"] for t in board["columns"][0]["tasks"]] == ["Задача"]
    assert ingest(client, part=1, title="X", board="нет такой").status_code == 404


def test_migrate_old_schema():
    """Старая БД: общие колонки с unique(name) и задачи — всё уходит на первую доску."""
    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import sessionmaker

    from app import models  # noqa: F401
    from app.database import Base
    from app.migrate import migrate
    from app.services.tasks import seed_boards

    engine = create_engine("sqlite://", poolclass=__import__("sqlalchemy").pool.StaticPool, connect_args={"check_same_thread": False})
    with engine.begin() as c:
        c.execute(text("CREATE TABLE board_columns (id INTEGER PRIMARY KEY, name VARCHAR(64) NOT NULL UNIQUE, position INTEGER NOT NULL)"))
        c.execute(text("INSERT INTO board_columns VALUES (1,'To Do',0),(2,'Done',1)"))
    Base.metadata.create_all(engine)  # создаёт boards и остальные таблицы, board_columns остаётся старой
    with engine.begin() as c:
        c.execute(text("INSERT INTO tasks (title, description, column_id, position, priority, source, part, edited, created_at, updated_at) "
                       "VALUES ('старая', '', 2, 0, 'normal', 'manual', 0, 0, '2026-01-01', '2026-01-01')"))
    migrate(engine, "ЕПУТС")
    with sessionmaker(bind=engine)() as db:
        seed_boards(db, ("ЕПУТС", "КИПАРИСС"), ("A", "B"))
        rows = db.execute(text("SELECT b.name, c.name FROM board_columns c JOIN boards b ON b.id=c.board_id ORDER BY b.id, c.position")).all()
    assert rows == [("ЕПУТС", "To Do"), ("ЕПУТС", "Done"), ("ЕПУТС", "A"), ("ЕПУТС", "B"), ("КИПАРИСС", "A"), ("КИПАРИСС", "B")]
    with engine.connect() as c:
        assert c.execute(text("SELECT column_id FROM tasks")).scalar() == 2


def test_chat(client):
    assert client.get("/api/v1/chat/messages").json() == []
    a = client.post("/api/v1/chat/messages", json={"client_id": "c1", "author_name": "Аня", "text": " привет "}).json()
    b = client.post("/api/v1/chat/messages", json={"client_id": "c2", "text": "хай"}).json()
    assert (a["text"], b["author_name"]) == ("привет", "Гость")
    assert [m["id"] for m in client.get("/api/v1/chat/messages").json()] == [a["id"], b["id"]]
    assert [m["id"] for m in client.get(f"/api/v1/chat/messages?after_id={a['id']}").json()] == [b["id"]]
    assert client.post("/api/v1/chat/messages", json={"client_id": "c1", "text": ""}).status_code == 422

    online = client.post("/api/v1/chat/heartbeat", json={"client_id": "c3", "name": "Боря"}).json()
    assert {u["name"] for u in online} >= {"Боря", "Аня"}


def test_app_password(client, monkeypatch):
    from app.config import get_settings

    monkeypatch.setenv("APP_PASSWORD", "sesame")
    get_settings.cache_clear()
    try:
        assert client.get("/api/v1/board").status_code == 401
        assert client.get("/api/v1/auth/check", headers={"X-App-Password": "nope"}).status_code == 401
        ok = {"X-App-Password": "sesame"}
        assert client.get("/api/v1/auth/check", headers=ok).status_code == 200
        assert client.get("/api/v1/board", headers=ok).status_code == 200
        assert ingest(client).status_code == 201  # бот авторизуется своим ключом, а не паролем интерфейса
        assert client.get("/health").status_code == 200
    finally:
        monkeypatch.delenv("APP_PASSWORD")
        get_settings.cache_clear()

def test_call_signaling(client):
    with client.websocket_connect("/api/v1/call/ws?client_id=a-tab1&chat_id=a&name=Аня") as a:
        assert a.receive_json() == {"type": "peers", "peers": []}
        with client.websocket_connect("/api/v1/call/ws?client_id=b-tab1&chat_id=b&name=Боря") as b:
            assert b.receive_json() == {"type": "peers", "peers": [{"id": "a-tab1", "name": "Аня"}]}
            assert a.receive_json() == {"type": "joined", "id": "b-tab1", "name": "Боря"}
            online = client.post("/api/v1/chat/heartbeat", json={"client_id": "a", "name": "Аня"}).json()
            assert {u["client_id"]: u["in_call"] for u in online}["a"] is True
            b.send_json({"to": "a-tab1", "data": {"sdp": "x"}})
            assert a.receive_json() == {"type": "signal", "from": "b-tab1", "data": {"sdp": "x"}}
        assert a.receive_json() == {"type": "left", "id": "b-tab1"}


def test_call_requires_password(client, monkeypatch):
    from starlette.websockets import WebSocketDisconnect

    from app.config import get_settings

    monkeypatch.setenv("APP_PASSWORD", "sesame")
    get_settings.cache_clear()
    try:
        with pytest.raises(WebSocketDisconnect):
            with client.websocket_connect("/api/v1/call/ws?client_id=a&password=nope") as ws:
                ws.receive_json()
        with client.websocket_connect("/api/v1/call/ws?client_id=a&password=sesame") as ws:
            assert ws.receive_json()["type"] == "peers"
    finally:
        monkeypatch.delenv("APP_PASSWORD")
        get_settings.cache_clear()


def test_call_same_chat_user_in_two_tabs(client):
    """Два устройства с одинаковым отпечатком (chat_id) не выкидывают друг друга из созвона."""
    with client.websocket_connect("/api/v1/call/ws?client_id=t1&chat_id=same&name=A") as a:
        a.receive_json()
        with client.websocket_connect("/api/v1/call/ws?client_id=t2&chat_id=same&name=B") as b:
            assert b.receive_json()["peers"] == [{"id": "t1", "name": "A"}]
            assert a.receive_json()["type"] == "joined"


def test_ice_servers(client, monkeypatch):
    from app.config import get_settings

    assert client.get("/api/v1/call/ice").json()["iceServers"] == [{"urls": "stun:stun.l.google.com:19302"}]
    monkeypatch.setenv("TURN_SECRET", "s3")
    monkeypatch.setenv("TURN_HOST", "1.2.3.4")
    get_settings.cache_clear()
    try:
        turn = client.get("/api/v1/call/ice").json()["iceServers"][1]
        assert turn["urls"][0] == "turn:1.2.3.4:3478?transport=udp"
        assert turn["username"].endswith(":pulse") and turn["credential"]
    finally:
        monkeypatch.undo()
        get_settings.cache_clear()


def test_notes(client):
    assert client.get("/api/v1/notes").json() == []
    a = client.post("/api/v1/notes", json={"title": " Ссылки ", "text": "https://x.ru", "author_name": "Аня"}).json()
    assert (a["title"], a["author_name"]) == ("Ссылки", "Аня")
    b = client.patch(f"/api/v1/notes/{a['id']}", json={"text": "https://y.ru"}).json()
    assert (b["title"], b["text"]) == ("Ссылки", "https://y.ru")
    assert len(client.get("/api/v1/notes").json()) == 1
    assert client.delete(f"/api/v1/notes/{a['id']}").status_code == 204
    assert client.patch(f"/api/v1/notes/{a['id']}", json={"text": "x"}).status_code == 404


def test_sheet_import(client):
    from app.database import SessionLocal  # noqa: F401
    from app.services import sheet

    text = "Название,Дата выступления\nДоклад про ИИ,25.12.2026\nКруглый стол,2026-11-03 14:30\n,\nБез даты,скоро\n"
    rows = sheet.parse_rows(text)
    assert [(t, d and d.isoformat()) for t, _, d, _ in rows] == [
        ("Доклад про ИИ", "2026-12-25T12:00:00+00:00"),
        ("Круглый стол", "2026-11-03T14:30:00+00:00"),
        ("Без даты", None),
    ]
    assert sheet.csv_url("https://docs.google.com/spreadsheets/d/AbC_1/edit#gid=7").endswith("/AbC_1/export?format=csv&gid=7")

    from app.main import SessionLocal as TestSession  # подменён фикстурой на тестовую БД

    with TestSession() as db:
        assert sheet.import_rows(db, rows) == 3
        assert sheet.import_rows(db, rows) == 0  # повторно не дублирует
    board = next(b for b in client.get("/api/v1/boards").json() if b["name"] == "Презентации")
    col = next(c for c in client.get(f"/api/v1/board?board_id={board['id']}").json()["columns"] if c["name"] == "To Do")
    assert [t["title"] for t in col["tasks"]] == ["Доклад про ИИ", "Круглый стол", "Без даты"]


def test_sheet_archive_past(client):
    from app.main import SessionLocal as TestSession
    from app.services import sheet

    rows = [("Прошлая", "01.01.2020", sheet.parse_date("01.01.2020"), ""), ("Будущая", "01.01.2099", sheet.parse_date("01.01.2099"), "")]
    with TestSession() as db:
        sheet.import_rows(db, rows)
        assert sheet.archive_past(db) == 1
        assert sheet.archive_past(db) == 0
    board = next(b for b in client.get("/api/v1/boards").json() if b["name"] == "Презентации")
    cols = {c["name"]: [t["title"] for t in c["tasks"]] for c in client.get(f"/api/v1/board?board_id={board['id']}").json()["columns"]}
    assert cols["Done"] == ["Прошлая"] and cols["To Do"] == ["Будущая"]


def test_sheet_date_without_year_and_backfill(client):
    from app.main import SessionLocal as TestSession
    from app.services import sheet

    assert sheet.parse_date("16.11").isoformat() == "2026-11-16T12:00:00+00:00"
    assert sheet.parse_date("16.11 18:30").isoformat() == "2026-11-16T18:30:00+00:00"
    with TestSession() as db:
        sheet.import_rows(db, [("Доклад", "16.11", None, "")])  # как до исправления: дата не распознана
        sheet.import_rows(db, sheet.parse_rows("Название,Дата\nДоклад,16.11\n"))
        from app.models import Task
        t = db.query(Task).filter_by(title="Доклад").one()
        assert t.due_at is not None and t.description == ""


def test_sheet_link_from_third_column(client):
    from app.main import SessionLocal as TestSession
    from app.models import Task
    from app.services import sheet

    with TestSession() as db:
        sheet.import_rows(db, sheet.parse_rows("Название,Дата,Ссылка\nДоклад,16.11,\n"))
        assert db.query(Task).filter_by(title="Доклад").one().description == ""
        # ссылку добавили в таблицу позже — подтянется к уже созданной задаче, без дублей
        text = "Название,Дата,Ссылка\nДоклад,16.11,https://x.ru/p\n"
        sheet.import_rows(db, sheet.parse_rows(text))
        sheet.import_rows(db, sheet.parse_rows(text))
        assert db.query(Task).filter_by(title="Доклад").one().description == "Презентация: https://x.ru/p"


def test_sheet_hyperlink_replaces_cell_text(client):
    import io

    from openpyxl import Workbook

    from app.main import SessionLocal as TestSession
    from app.models import Task
    from app.services import sheet

    wb = Workbook()
    ws = wb.active
    ws.append(["Название", "Дата", "Ссылка"])
    ws.append(["Доклад", "16.11", "Слайды"])
    ws["C2"].hyperlink = "https://x.ru/slides"
    buf = io.BytesIO()
    wb.save(buf)
    links = sheet.parse_xlsx_links(buf.getvalue())
    assert links == {1: "https://x.ru/slides"}

    csv_text = "Название,Дата,Ссылка\nДоклад,16.11,Слайды\n"
    with TestSession() as db:
        sheet.import_rows(db, sheet.parse_rows(csv_text))  # как раньше: в описании только текст ячейки
        assert db.query(Task).one().description == "Презентация: Слайды"
        sheet.import_rows(db, sheet.parse_rows(csv_text, links))
        assert db.query(Task).one().description == "Презентация: https://x.ru/slides"


def test_sheet_sync_endpoint(client, monkeypatch):
    from app.api import sheet as sheet_api
    from app.config import get_settings

    assert client.get("/api/v1/sheet").json() == {"enabled": False}
    assert client.post("/api/v1/sheet/sync").status_code == 404

    monkeypatch.setattr(get_settings(), "sheet_url", "https://docs.google.com/spreadsheets/d/x/edit")
    monkeypatch.setattr(sheet_api.sheet, "sync_once", lambda: (2, 1))
    assert client.get("/api/v1/sheet").json() == {"enabled": True}
    assert client.post("/api/v1/sheet/sync").json() == {"created": 2, "archived": 1}

    def boom():
        raise RuntimeError("нет доступа")

    monkeypatch.setattr(sheet_api.sheet, "sync_once", boom)
    assert client.post("/api/v1/sheet/sync").status_code == 502
