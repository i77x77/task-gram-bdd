# TaskGram Backend

FastAPI-бэкенд: принимает задачи от [TaskGramTgBot](../TaskGramTgBot), хранит в SQLite и отдаёт API для канбан-доски.

## Архитектура

```
app/
  main.py            # приложение, lifespan (create_all + сид колонок), CORS, обработчики ошибок
  config.py          # настройки из .env
  database.py        # engine SQLite (WAL, foreign_keys), UTCDateTime, get_db
  models.py          # User, Chat, BoardColumn, Task, Tag, Attachment
  schemas.py         # Pydantic: контракт бота + DTO фронта
  security.py        # Bearer-ключ для /ingest
  api/               # тонкие роутеры: ingest, tasks, board (колонки/доска/теги)
  services/          # бизнес-логика: ingest (upsert из Telegram), tasks (позиции, перенос)
tests/               # pytest, in-memory SQLite
```

Модель данных: `users`, `chats`, `board_columns` (name, position), `tasks` (column_id, position, priority, due_at,
источник и метаданные Telegram), `tags` + `task_tags`, `attachments`.

Решения:
- **Идемпотентность:** `UNIQUE(chat_id, message_id)`. Повтор без `edited` → `duplicate`, ничего не меняется;
  `edited: true` → обновляются текст, теги, вложения, но колонка и позиция на доске сохраняются.
- **Заголовок/описание:** первая строка текста — `title` (до 200 символов), остальное — `description`.
  Без текста — `[document] file.pdf`.
- **Хэштеги → теги** (без `#`, в нижнем регистре). Пользователь — по `author.id`.
- **Время:** UTC; в SQLite хранится naive UTC, наружу отдаётся с таймзоной.
- **Порядок на доске:** `position` — плотный индекс 0..n-1 внутри колонки, пересчитывается при переносе/удалении.
- Новые задачи попадают в первую колонку (по умолчанию `To Do / In Progress / Done`).

## Запуск

```bash
cp .env.example .env
python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
.venv/bin/uvicorn app.main:app --reload      # http://localhost:8000/docs
.venv/bin/pytest
```
Docker: `docker compose up -d --build` (БД в `./data`).

## API (`/api/v1`)

| Метод | Путь | Назначение |
|---|---|---|
| POST | `/ingest/telegram` | Приём JSON от бота (`Authorization: Bearer $INGEST_API_KEY`). 201 `created`, 200 `updated`/`duplicate` |
| GET | `/board` | Вся доска: колонки с задачами. Фильтры `tag`, `author_id`, `q` |
| GET/POST | `/columns` | Список / создание колонки |
| PATCH/DELETE | `/columns/{id}` | Переименование, смена позиции / удаление (`?move_to=<id>`, если есть задачи) |
| GET/POST | `/tasks` | Список (`column_id, tag, author_id, chat_id, priority, q, limit, offset`) / ручное создание |
| GET/PATCH/DELETE | `/tasks/{id}` | Чтение / правка (title, description, priority, due_at, tags) / удаление |
| POST | `/tasks/{id}/move` | Drag-and-drop: `{"column_id": 2, "position": 0}` |
| GET | `/tags` | Теги со счётчиком |
| GET | `/health` | Проверка живости |

Swagger: `/docs`.

## Подключение бота

В `TaskGramTgBot` заменить `send_to_backend`:

```python
async def send_to_backend(task: dict) -> None:
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.post(f"{BACKEND_URL}/api/v1/ingest/telegram", json=task,
                              headers={"Authorization": f"Bearer {API_KEY}"})
        r.raise_for_status()
```
Любой 2xx — принято; повторные отправки безопасны (идемпотентность).

## Не сделано (осознанно)
- Авторизация фронта (сейчас только CORS); миграции Alembic (схема создаётся через `create_all`);
  скачивание файлов по `file_id` (нужен токен бота).
