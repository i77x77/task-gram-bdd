import os

os.environ["DATABASE_URL"] = "sqlite://"
os.environ["INGEST_API_KEY"] = "secret"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool

from app import database
from app.main import app


@pytest.fixture
def client(monkeypatch):
    engine = database.create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    from sqlalchemy.orm import sessionmaker

    TestSession = sessionmaker(bind=engine, expire_on_commit=False)
    monkeypatch.setattr("app.main.engine", engine)
    monkeypatch.setattr("app.main.SessionLocal", TestSession)

    def override():
        with TestSession() as s:
            yield s

    app.dependency_overrides[database.get_db] = override
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
    database.Base.metadata.drop_all(engine)


def tg_payload(**over):
    base = {
        "text": "Купить молоко #дом https://x.ru",
        "sent_at": "2026-10-21T09:06:18.379901+00:00",
        "sent_at_unix": 1792573578,
        "author": {"id": 5, "username": "art", "first_name": "Artur", "last_name": None,
                   "full_name": "Artur", "language_code": "ru", "is_premium": False},
        "chat": {"id": 5, "type": "private", "title": None},
        "message_id": 1,
        "entities": {"hashtags": ["#дом"], "mentions": [], "links": ["https://x.ru"], "commands": []},
        "attachments": [],
        "forwarded_from": None,
        "reply_to": None,
        "edited": False,
    }
    base.update(over)
    return base


AUTH = {"Authorization": "Bearer secret"}
