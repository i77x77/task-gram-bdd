import asyncio
import json
import logging
import os

import httpx

LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://vyceai.com/v1")
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_MODEL = os.getenv("LLM_MODEL", "DeepSeek-V4.1-Flash")
LLM_TIMEOUT = float(os.getenv("LLM_TIMEOUT", "60"))
LLM_RETRIES = 3
MAX_TASKS = 20
PRIORITIES = {"low", "normal", "high", "urgent"}

SYSTEM_PROMPT = """Ты разбираешь сообщения из Telegram и превращаешь их в задачи для канбан-доски.
В одном сообщении может быть несколько разных задач, причём без чётких разделителей, \
с опечатками и в разговорной форме. Определи, где заканчивается одна задача и начинается другая.

Для каждой задачи:
- title: короткая чёткая формулировка действия (до 80 символов), с глагола в неопределённой форме \
или императиве, без лишних слов. Язык — как в исходном сообщении.
- description: детали, срок, контекст из сообщения; пустая строка, если добавить нечего. \
Ничего не выдумывай.
- priority: low | normal | high | urgent. По умолчанию normal; high/urgent только если это ясно из текста \
(«срочно», «горит», «до вечера» и т.п.).

Если в сообщении нет задач (приветствие, болтовня), верни пустой список.
Ответ — строго JSON без пояснений и markdown:
{"tasks": [{"title": "...", "description": "...", "priority": "normal"}]}"""


def _clean(items: object) -> list[dict]:
    tasks = []
    for item in items if isinstance(items, list) else []:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "").strip()
        if not title:
            continue
        priority = str(item.get("priority") or "normal").lower()
        tasks.append({
            "title": title[:200],
            "description": str(item.get("description") or "").strip(),
            "priority": priority if priority in PRIORITIES else "normal",
        })
    return tasks[:MAX_TASKS]


def _parse(content: str) -> list[dict]:
    # Модель может обернуть JSON в markdown или добавить пояснение — берём от первой { до последней }
    start, end = content.find("{"), content.rfind("}")
    data = json.loads(content[start:end + 1])
    return _clean(data.get("tasks"))


async def extract_tasks(text: str) -> list[dict] | None:
    """Разбирает текст на задачи через LLM. None — LLM недоступна или ответила мусором."""
    body = {
        "model": LLM_MODEL,
        "messages": [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": text}],
        "temperature": 0,
    }
    headers = {"Authorization": f"Bearer {LLM_API_KEY}"}
    for attempt in range(LLM_RETRIES):
        try:
            async with httpx.AsyncClient(timeout=LLM_TIMEOUT) as client:
                r = await client.post(f"{LLM_BASE_URL}/chat/completions", json=body, headers=headers)
            if r.status_code in (429, 500, 502, 503, 504):
                logging.warning("LLM busy (%d), attempt %d", r.status_code, attempt + 1)
                await asyncio.sleep(2 * (attempt + 1))
                continue
            r.raise_for_status()
            return _parse(r.json()["choices"][0]["message"]["content"])
        except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError) as e:
            logging.warning("LLM extraction failed: %r", e)
            return None
    return None
