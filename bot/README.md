# TaskGram Telegram Bot

Telegram-бот, который принимает задачи сообщениями, превращает каждое сообщение в структурированный JSON и передаёт его на бэкенд. JSON отправляется на бэкенд (`POST /api/v1/ingest/telegram`), см. [../backend](../backend).

## Стек

- Python 3.13
- [aiogram 3](https://docs.aiogram.dev/) (long polling)
- python-dotenv
- Docker / docker-compose

## Структура проекта

| Файл | Назначение |
|---|---|
| `bot.py` | Вся логика бота |
| `requirements.txt` | Зависимости |
| `.env.example` | Шаблон переменных окружения |
| `Dockerfile`, `docker-compose.yml` | Запуск в контейнере |

## Конфигурация

| Переменная | Описание |
|---|---|
| `BOT_TOKEN` | Токен бота от @BotFather (обязательная) |

| `BACKEND_URL` | Адрес бэкенда (по умолчанию `http://localhost:8000`; в compose — `http://backend:8000`) |
| `INGEST_API_KEY` | Общий секрет с бэкендом |

## Запуск

Docker (рекомендуется):
```bash
cp .env.example .env     # вписать BOT_TOKEN
docker compose up -d --build
docker compose logs -f
```

Локально:
```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python bot.py
```

Один токен можно опрашивать только из одного места, иначе будет `TelegramConflictError`.

## Поведение бота

- `/start` — приветствие.
- Любое другое сообщение (текст, фото с подписью, документ и т. д.) считается задачей: бот собирает JSON, вызывает `send_to_backend(task)` и отвечает «✅ Задача принята».
- Редактирование сообщения в Telegram — бот отправляет задачу повторно с `edited: true` и отвечает «✏️ Задача обновлена».
- Сообщения без `from_user` (например, от каналов) игнорируются.

## Формат JSON (контракт для бэкенда)

Пример:

```json
{
  "text": "Купить молоко #дом https://x.ru",
  "sent_at": "2026-10-21T09:06:18.379901+00:00",
  "sent_at_unix": 1792573578,
  "author": {
    "id": 5,
    "username": "art",
    "first_name": "Artur",
    "last_name": null,
    "full_name": "Artur",
    "language_code": "ru",
    "is_premium": false
  },
  "chat": { "id": 5, "type": "private", "title": null },
  "message_id": 1,
  "entities": {
    "hashtags": ["#дом"],
    "mentions": [],
    "links": ["https://x.ru"],
    "commands": []
  },
  "attachments": [],
  "forwarded_from": null,
  "reply_to": null,
  "edited": false
}
```

### Поля

| Поле | Тип | Описание |
|---|---|---|
| `text` | string | Текст задачи; для вложений — подпись (caption), может быть `""` |
| `sent_at` | string (ISO 8601, UTC) | Время отправки сообщения |
| `sent_at_unix` | int | То же время, Unix timestamp (секунды) |
| `author.id` | int | Telegram ID пользователя (стабильный идентификатор) |
| `author.username` | string \| null | `@username` без `@` |
| `author.first_name` / `last_name` / `full_name` | string \| null | Имя автора |
| `author.language_code` | string \| null | Язык интерфейса, напр. `ru` |
| `author.is_premium` | bool | Есть ли Telegram Premium |
| `chat.id` | int | ID чата (в личке совпадает с `author.id`; в группах отрицательный) |
| `chat.type` | string | `private`, `group`, `supergroup`, `channel` |
| `chat.title` | string \| null | Название группы (в личке `null`) |
| `message_id` | int | ID сообщения; уникален в рамках `chat.id` |
| `entities.hashtags` | string[] | Хэштеги вместе с `#` |
| `entities.mentions` | string[] | Упоминания вместе с `@` |
| `entities.links` | string[] | Ссылки |
| `entities.commands` | string[] | Bot-команды |
| `attachments` | object[] | Вложения, см. ниже |
| `forwarded_from` | object \| null | Источник пересланного сообщения (структура `MessageOrigin` из Telegram Bot API) |
| `reply_to` | `{message_id, text}` \| null | Сообщение, на которое ответили |
| `edited` | bool | `true`, если это отредактированное сообщение |

### Вложения (`attachments[]`)

Типы `type`: `photo`, `document`, `video`, `voice`, `audio`, `video_note`, `animation`, `sticker`:

```json
{
  "type": "document",
  "file_id": "...",
  "file_unique_id": "...",
  "file_name": "spec.pdf",
  "mime_type": "application/pdf",
  "file_size": 12345
}
```

Также бывают `location` (`latitude`, `longitude`) и `contact` (`phone_number`, `name`).

Важно: `file_id` — это идентификатор файла внутри Telegram, а не ссылка. Само содержимое бот не скачивает. Чтобы получить файл, нужен вызов Bot API `getFile` с токеном бота.

## Рекомендации для бэкенда

- **Идемпотентность / дедупликация:** ключ задачи — пара `(chat.id, message_id)`. При `edited: true` обновлять существующую задачу, а не создавать новую.
- **Пользователь:** идентифицировать по `author.id`, а не по `username` (он может меняться или отсутствовать).
- **Время:** хранить в UTC (`sent_at`), в часовой пояс пользователя переводить на клиенте. Telegram не передаёт часовой пояс пользователя.
- **Теги:** `entities.hashtags` можно использовать как теги/проекты задачи.
- **Ответ:** бот пока не анализирует ответ бэкенда; при подключении стоит договориться о коде ответа (2xx — принято) и политике ретраев.

## Точка интеграции

`send_to_backend(task)` в `bot.py` делает POST на `$BACKEND_URL/api/v1/ingest/telegram` с `Authorization: Bearer $INGEST_API_KEY`, 3 попытки с паузой; при неудаче бот отвечает «⚠️ Бэкенд недоступен». Повторы безопасны — бэкенд идемпотентен по `(chat.id, message_id)`.

## Планы

- Разбор дедлайнов («завтра в 18:00») и приоритетов из текста.
- Команды для просмотра/закрытия задач (после появления API бэкенда).
