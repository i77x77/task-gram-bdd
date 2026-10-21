import asyncio
import json
import logging
import os
from datetime import timezone

from aiogram import Bot, Dispatcher
from aiogram.filters import CommandStart
from aiogram.types import Message
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO)
dp = Dispatcher()

ATTACHMENT_TYPES = ("photo", "document", "video", "voice", "audio", "video_note", "animation", "sticker")


def extract_entities(message: Message) -> dict:
    text = message.text or message.caption or ""
    result = {"hashtags": [], "mentions": [], "links": [], "commands": []}
    for e in message.entities or message.caption_entities or []:
        chunk = text[e.offset:e.offset + e.length]
        if e.type == "hashtag":
            result["hashtags"].append(chunk)
        elif e.type == "mention":
            result["mentions"].append(chunk)
        elif e.type == "url":
            result["links"].append(chunk)
        elif e.type == "text_link":
            result["links"].append(e.url)
        elif e.type == "bot_command":
            result["commands"].append(chunk)
    return result


def extract_attachments(message: Message) -> list[dict]:
    items = []
    for kind in ATTACHMENT_TYPES:
        obj = getattr(message, kind, None)
        if not obj:
            continue
        if kind == "photo":
            obj = obj[-1]  # largest size
        items.append({
            "type": kind,
            "file_id": obj.file_id,
            "file_unique_id": obj.file_unique_id,
            "file_name": getattr(obj, "file_name", None),
            "mime_type": getattr(obj, "mime_type", None),
            "file_size": getattr(obj, "file_size", None),
        })
    if message.location:
        items.append({"type": "location", "latitude": message.location.latitude,
                      "longitude": message.location.longitude})
    if message.contact:
        items.append({"type": "contact", "phone_number": message.contact.phone_number,
                      "name": message.contact.first_name})
    return items


def build_task(message: Message) -> dict:
    user = message.from_user
    chat = message.chat
    sent_at = message.date.astimezone(timezone.utc)
    forward = message.forward_origin
    reply = message.reply_to_message

    return {
        "text": message.text or message.caption or "",
        "sent_at": sent_at.isoformat(),
        "sent_at_unix": int(sent_at.timestamp()),
        "author": {
            "id": user.id,
            "username": user.username,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "full_name": user.full_name,
            "language_code": user.language_code,
            "is_premium": bool(user.is_premium),
        },
        "chat": {
            "id": chat.id,
            "type": chat.type,
            "title": chat.title,
        },
        "message_id": message.message_id,
        "entities": extract_entities(message),
        "attachments": extract_attachments(message),
        "forwarded_from": forward.model_dump(mode="json", exclude_none=True) if forward else None,
        "reply_to": {
            "message_id": reply.message_id,
            "text": reply.text or reply.caption,
        } if reply else None,
        "edited": message.edit_date is not None,
    }


def send_to_backend(task: dict) -> None:
    # TODO: заменить на HTTP-запрос к беку (httpx.post(BACKEND_URL, json=task))
    print(json.dumps(task, ensure_ascii=False, indent=2), flush=True)


@dp.message(CommandStart())
async def start(message: Message):
    await message.answer("Привет! Отправь мне задачу текстом — я её запишу.")


@dp.message()
async def on_task(message: Message):
    if not message.from_user:
        return
    send_to_backend(build_task(message))
    await message.answer("✅ Задача принята")


@dp.edited_message()
async def on_edit(message: Message):
    if not message.from_user:
        return
    send_to_backend(build_task(message))
    await message.answer("✏️ Задача обновлена")


async def main():
    bot = Bot(os.environ["BOT_TOKEN"])
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
