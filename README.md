# TaskGram

Задачи из Telegram → канбан-доска.

| Каталог | Что это |
|---|---|
| [`bot/`](bot/README.md) | Telegram-бот (aiogram): превращает сообщения в JSON и шлёт на бэкенд |
| [`backend/`](backend/README.md) | FastAPI + SQLite: принимает задачи от бота, отдаёт API для канбан-доски |

## Запуск всего через Docker

```bash
cp .env.example .env     # BOT_TOKEN и INGEST_API_KEY
docker compose up -d --build
docker compose logs -f
```

- Бэкенд: http://localhost:8000 (Swagger — `/docs`), база в volume `backend-data`.
- Бот стартует после того, как бэкенд прошёл healthcheck, и ходит к нему по `http://backend:8000`.
- Один токен бота можно опрашивать только из одного места (иначе `TelegramConflictError`).

## Frontend (канбан-доска)

React + TypeScript + Vite, drag-and-drop на `@dnd-kit`. Папка `frontend/`.

```bash
cd frontend && npm install && npm run dev   # http://localhost:5173, /api проксируется на :8000
```
В Docker: `docker compose up -d --build` → http://localhost:3000 (nginx отдаёт статику и проксирует `/api` на бэкенд).
Доска сама опрашивает бэкенд раз в 10 секунд, поэтому новые задачи из Telegram появляются без перезагрузки.
