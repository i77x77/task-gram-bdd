"""Голосовой созвон: сервер только пересылает WebRTC-сигналы (offer/answer/ICE), звук идёт напрямую между браузерами."""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter(prefix="/call", tags=["call"])

# client_id -> (websocket, имя); комната одна на всё приложение
participants: dict[str, tuple[WebSocket, str]] = {}


async def _send(ws: WebSocket, message: dict) -> None:
    try:
        await ws.send_json(message)
    except Exception:  # клиент уже ушёл — его чистит собственный обработчик
        pass


@router.websocket("/ws")
async def call_ws(ws: WebSocket, client_id: str, name: str = ""):
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

    peers = [{"id": cid, "name": n} for cid, (_, n) in participants.items()]
    participants[client_id] = (ws, name)
    await _send(ws, {"type": "peers", "peers": peers})
    for cid, (other, _) in list(participants.items()):
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
            for other, _ in list(participants.values()):
                await _send(other, {"type": "left", "id": client_id})
