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
  const openRef = useRef(open);
  openRef.current = open;

  const poll = useCallback(async () => {
    try {
      const fresh = await api.chatMessages(lastId.current);
      if (fresh.length) {
        lastId.current = fresh[fresh.length - 1].id;
        setMessages((m) => [...m, ...fresh]);
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
        <section className="chat-panel" aria-label="Общий чат">
          <header className="chat-head">
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
