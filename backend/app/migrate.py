"""Лёгкие миграции схемы SQLite: create_all не меняет уже существующие таблицы."""
from sqlalchemy import Engine, inspect, text


def migrate(engine: Engine, first_board: str) -> None:
    insp = inspect(engine)
    if "author_name" not in {c["name"] for c in insp.get_columns("tasks")}:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE tasks ADD COLUMN author_name VARCHAR(100)"))

    if "board_id" not in {c["name"] for c in insp.get_columns("board_columns")}:
        _add_boards(engine, first_board)


def _add_boards(engine: Engine, first_board: str) -> None:
    """Колонки были общими на всё приложение и с уникальным name: пересоздаём таблицу
    (SQLite не умеет менять ограничения) и отдаём все старые колонки с задачами первой доске."""
    raw = engine.raw_connection()
    try:
        cur = raw.cursor()
        cur.execute("PRAGMA foreign_keys=OFF")  # вне транзакции, иначе no-op
        cur.execute("INSERT OR IGNORE INTO boards (name, position) VALUES (?, 0)", (first_board,))
        cur.execute(
            """CREATE TABLE board_columns__new (
                id INTEGER NOT NULL PRIMARY KEY,
                board_id INTEGER NOT NULL REFERENCES boards (id) ON DELETE CASCADE,
                name VARCHAR(64) NOT NULL,
                position INTEGER NOT NULL,
                CONSTRAINT uq_column_board_name UNIQUE (board_id, name)
            )"""
        )
        cur.execute(
            "INSERT INTO board_columns__new (id, board_id, name, position) "
            "SELECT id, (SELECT id FROM boards WHERE name = ?), name, position FROM board_columns",
            (first_board,),
        )
        cur.execute("DROP TABLE board_columns")
        cur.execute("ALTER TABLE board_columns__new RENAME TO board_columns")
        raw.commit()
        cur.execute("PRAGMA foreign_keys=ON")
    finally:
        raw.close()
