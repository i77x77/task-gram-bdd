import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../api/client";
import type { ChatMessage, OnlineUser } from "../api/types";

const MSG_POLL_MS = 3_000;
const BEAT_MS = 10_000;

function clientId(): string {
  try {
    let id = localStorage.getItem("clientId");
    if (!id) {
      id = crypto.randomUUID();
      localStorage.setItem("clientId", id);
    }
    return id;
  } catch {
    return Math.random().toString(36).slice(2);
  }
}

const ME = clientId();

/** Общий чат: все, у кого открыта доска, видят одни и те же сообщения и список «онлайн». */
export function ChatPanel({ userName }: { userName: string }) {
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [online, setOnline] = useState<OnlineUser[]>([]);
  const [text, setText] = useState("");
  const [seen, setSeen] = useState(0); // id последнего прочитанного сообщения
  const lastId = useRef(0);
  const list = useRef<HTMLDivElement>(null);
  const [pos, setPos] = useState<{ x: number; y: number } | null>(() => {
    try {
      return JSON.parse(localStorage.getItem("chatPos") ?? "null");
    } catch {
      return null;
    }
  });
  const panel = useRef<HTMLElement>(null);

  const startDrag = (e: React.PointerEvent) => {
    const el = panel.current;
    if (!el || e.button !== 0) return;
    const r = el.getBoundingClientRect();
    const dx = e.clientX - r.left;
    const dy = e.clientY - r.top;
    let last = { x: r.left, y: r.top };
    const move = (ev: PointerEvent) => {
      last = {
        x: Math.min(Math.max(ev.clientX - dx, 0), window.innerWidth - r.width),
        y: Math.min(Math.max(ev.clientY - dy, 0), window.innerHeight - r.height),
      };
      setPos(last);
    };
    const up = () => {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", up);
      try {
        localStorage.setItem("chatPos", JSON.stringify(last));
      } catch {
        /* позиция просто не запомнится */
      }
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up);
  };
  const openRef = useRef(open);
  openRef.current = open;

  const poll = useCallback(async () => {
    try {
      const fresh = await api.chatMessages(lastId.current);
      // Опрос и отправка могут получить одно и то же сообщение одновременно — отбрасываем уже добавленные
      const added = fresh.filter((m) => m.id > lastId.current);
      if (added.length) {
        lastId.current = added[added.length - 1].id;
        setMessages((m) => [...m, ...added]);
      }
    } catch {
      /* чат второстепенен: ошибки сети не показываем */
    }
  }, []);

  useEffect(() => {
    void poll();
    const i = setInterval(poll, MSG_POLL_MS);
    return () => clearInterval(i);
  }, [poll]);

  useEffect(() => {
    const beat = () => api.heartbeat(ME, userName).then(setOnline, () => {});
    void beat();
    const i = setInterval(beat, BEAT_MS);
    return () => clearInterval(i);
  }, [userName]);

  useEffect(() => {
    if (open && messages.length) {
      setSeen(messages[messages.length - 1].id);
      list.current?.scrollTo({ top: list.current.scrollHeight });
    }
  }, [open, messages]);

  const unread = messages.filter((m) => m.id > seen && m.client_id !== ME).length;

  const send = async () => {
    const t = text.trim();
    if (!t) return;
    setText("");
    try {
      await api.sendChatMessage(ME, userName, t);
      await poll();
    } catch {
      setText(t);
    }
  };

  return (
    <>
      <button className="chat-fab" onClick={() => setOpen(!open)} aria-label="Общий чат" aria-expanded={open}>
        💬{unread > 0 && <span className="chat-badge">{unread}</span>}
      </button>
      {open && (
        <section
          ref={panel}
          className="chat-panel"
          aria-label="Общий чат"
          style={pos ? { left: Math.min(pos.x, window.innerWidth - 120), top: Math.min(pos.y, window.innerHeight - 60), right: "auto", bottom: "auto" } : undefined}
        >
          <header className="chat-head" onPointerDown={startDrag} title="Перетащите, чтобы переместить">
            <b>Общий чат</b>
            <span className="muted">онлайн: {online.length}</span>
          </header>
          <div className="chat-online">
            {online.map((u) => (
              <span key={u.client_id} className={`chat-user${u.client_id === ME ? " me" : ""}`}>
                {u.name}
              </span>
            ))}
          </div>
          <div className="chat-list" ref={list}>
            {messages.length === 0 && <div className="muted">Сообщений пока нет</div>}
            {messages.map((m) => (
              <div key={m.id} className={`chat-msg${m.client_id === ME ? " mine" : ""}`}>
                <div className="chat-meta">
                  {m.author_name} · {new Date(m.created_at).toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit" })}
                </div>
                <div className="chat-text">{m.text}</div>
              </div>
            ))}
          </div>
          <form
            className="chat-form"
            onSubmit={(e) => {
              e.preventDefault();
              void send();
            }}
          >
            <input placeholder="Сообщение…" value={text} maxLength={2000} onChange={(e) => setText(e.target.value)} />
            <button className="primary" type="submit" disabled={!text.trim()}>
              ➤
            </button>
          </form>
        </section>
      )}
    </>
  );
}
