"""Голосовой созвон: сервер только пересылает WebRTC-сигналы (offer/answer/ICE), звук идёт напрямую между браузерами."""
import base64
import hashlib
import hmac
import secrets
import time

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect

from app.config import get_settings
from app.security import require_app_password

router = APIRouter(prefix="/call", tags=["call"])

# id вкладки в созвоне -> (websocket, имя, id в чате); комната одна на всё приложение
participants: dict[str, tuple[WebSocket, str, str]] = {}

TURN_TTL = 12 * 3600  # время жизни временных TURN-учёток, сек


async def _send(ws: WebSocket, message: dict) -> None:
    try:
        await ws.send_json(message)
    except Exception:  # клиент уже ушёл — его чистит собственный обработчик
        pass


@router.websocket("/ws")
async def call_ws(ws: WebSocket, client_id: str, name: str = "", password: str = "", chat_id: str = ""):
    expected = get_settings().app_password
    if expected and not secrets.compare_digest(password.encode(), expected.encode()):
        await ws.close(code=1008)
        return
    if not client_id or len(client_id) > 64:
        await ws.close(code=1008)
        return
    await ws.accept()
    name = name.strip()[:100] or "Гость"

    old = participants.pop(client_id, None)  # та же вкладка переподключилась / открыта вторая
    if old:
        try:
            await old[0].close(code=4000)
        except Exception:
            pass

    peers = [{"id": cid, "name": n} for cid, (_, n, _) in participants.items()]
    participants[client_id] = (ws, name, chat_id[:64])
    await _send(ws, {"type": "peers", "peers": peers})
    for cid, (other, _, _) in list(participants.items()):
        if cid != client_id:
            await _send(other, {"type": "joined", "id": client_id, "name": name})

    try:
        while True:
            msg = await ws.receive_json()
            target = participants.get(str(msg.get("to")))
            if target and msg.get("data") is not None:
                await _send(target[0], {"type": "signal", "from": client_id, "data": msg["data"]})
    except (WebSocketDisconnect, RuntimeError, ValueError):
        pass
    finally:
        if participants.get(client_id, (None,))[0] is ws:
            del participants[client_id]
            for other, _, _ in list(participants.values()):
                await _send(other, {"type": "left", "id": client_id})


@router.get("/ice", dependencies=[Depends(require_app_password)])
def ice_servers():
    """STUN + (если настроен TURN) временные учётные данные для coturn (use-auth-secret)."""
    s = get_settings()
    servers: list[dict] = [{"urls": "stun:stun.l.google.com:19302"}]
    if s.turn_secret and s.turn_host:
        username = f"{int(time.time()) + TURN_TTL}:pulse"
        digest = hmac.new(s.turn_secret.encode(), username.encode(), hashlib.sha1).digest()
        host = f"{s.turn_host}:{s.turn_port}"
        servers.append(
            {
                "urls": [f"turn:{host}?transport=udp", f"turn:{host}?transport=tcp"],
                "username": username,
                "credential": base64.b64encode(digest).decode(),
            }
        )
    return {"iceServers": servers}
