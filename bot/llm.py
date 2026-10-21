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

SYSTEM_PROMPT = """Ты разбираешь сообщения из Telegram и превращаешь их в аккуратные задачи для канбан-доски.
В одном сообщении может быть несколько разных задач, причём без чётких разделителей, \
с опечатками и в разговорной форме. Определи, где заканчивается одна задача и начинается другая.

Для каждой задачи:
- title: короткая чёткая формулировка действия (до 80 символов): исправь опечатки и грамматику, \
убери слова-паразиты и мусор, начни с глагола, с заглавной буквы, без точки в конце. \
Язык — как в исходном сообщении.
- description: детали, срок, контекст из сообщения, аккуратно и без воды; пустая строка, если добавить нечего. \
Ничего не выдумывай.
- priority: low | normal | high | urgent. По умолчанию normal; high/urgent только если это ясно из текста \
(«срочно», «горит», «до вечера» и т.п.).
- column: колонка доски, в которую положить задачу, определи по смыслу.

Колонки на доске сейчас: {columns}.
Правила выбора колонки:
- Обычная новая задача — в первую колонку.
- Если из текста видно, что работа уже идёт — в колонку про «в работе»; если уже сделано — в колонку про «готово».
- Если задача «когда-нибудь», «на будущее», «потом», «идея», «не срочно, но хорошо бы» — в колонку Backlog.
- Всегда используй имя существующей колонки точно как в списке. Если подходящей нет (например, нет Backlog \
для отложенной задачи), укажи короткое имя новой колонки — она будет создана. \
Не создавай новые колонки без необходимости.

Если в сообщении нет задач (приветствие, болтовня), верни пустой список.
Ответ — строго JSON без пояснений и markdown:
{"tasks": [{"title": "...", "description": "...", "priority": "normal", "column": "..."}]}"""


def _clean(items: object) -> list[dict]:
    tasks = []
    for item in items if isinstance(items, list) else []:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "").strip()
        if not title:
            continue
        priority = str(item.get("priority") or "normal").lower()
        column = str(item.get("column") or "").strip()[:64]
        tasks.append({
            "title": title[:200],
            "column": column or None,
            "description": str(item.get("description") or "").strip(),
            "priority": priority if priority in PRIORITIES else "normal",
        })
    return tasks[:MAX_TASKS]


def _parse(content: str) -> list[dict]:
    # Модель может обернуть JSON в markdown или добавить пояснение — берём от первой { до последней }
    start, end = content.find("{"), content.rfind("}")
    data = json.loads(content[start:end + 1])
    return _clean(data.get("tasks"))


async def extract_tasks(text: str, columns: list[str]) -> list[dict] | None:
    """Разбирает текст на задачи через LLM. None — LLM недоступна или ответила мусором."""
    prompt = SYSTEM_PROMPT.replace("{columns}", ", ".join(columns) or "пока нет")
    body = {
        "model": LLM_MODEL,
        "messages": [{"role": "system", "content": prompt}, {"role": "user", "content": text}],
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
