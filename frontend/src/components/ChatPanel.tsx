import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../api/client";
import type { ChatMessage, OnlineUser } from "../api/types";

const MSG_POLL_MS = 3_000;
const BEAT_MS = 10_000;

/** Быстрый несекретный хеш (cyrb53): crypto.subtle недоступен на http, а нам нужен лишь стабильный id. */
function hash(str: string): string {
  let h1 = 0xdeadbeef;
  let h2 = 0x41c6ce57;
  for (let i = 0; i < str.length; i++) {
    const c = str.charCodeAt(i);
    h1 = Math.imul(h1 ^ c, 2654435761);
    h2 = Math.imul(h2 ^ c, 1597334677);
  }
  h1 = Math.imul(h1 ^ (h1 >>> 16), 2246822507) ^ Math.imul(h2 ^ (h2 >>> 13), 3266489909);
  h2 = Math.imul(h2 ^ (h2 >>> 16), 2246822507) ^ Math.imul(h1 ^ (h1 >>> 13), 3266489909);
  return (4294967296 * (2097151 & h2) + (h1 >>> 0)).toString(36);
}

function canvasPrint(): string {
  try {
    const c = document.createElement("canvas");
    const g = c.getContext("2d");
    if (!g) return "";
    g.textBaseline = "top";
    g.font = "14px Arial";
    g.fillStyle = "#f60";
    g.fillRect(10, 1, 60, 20);
    g.fillStyle = "#069";
    g.fillText("TaskGram, привет 🙂", 2, 2);
    return c.toDataURL();
  } catch {
    return "";
  }
}

/** Отпечаток браузера: один и тот же после перезагрузки, даже если localStorage очищен или недоступен. */
function clientId(): string {
  const n = navigator;
  const parts = [
    n.userAgent,
    n.language,
    n.languages?.join(","),
    n.platform,
    n.hardwareConcurrency,
    screen.width,
    screen.height,
    screen.colorDepth,
    devicePixelRatio,
    Intl.DateTimeFormat().resolvedOptions().timeZone,
    canvasPrint(),
  ];
  return `fp-${hash(parts.join("|"))}`;
}

const ME = clientId();

/** Общий чат в стиле Dynamic Island: компактная «таблетка» сверху, по клику раскрывается в чат. */
export function ChatPanel({ userName }: { userName: string }) {
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [online, setOnline] = useState<OnlineUser[]>([]);
  const [text, setText] = useState("");
  const [seen, setSeen] = useState(0); // id последнего прочитанного сообщения
  const [peek, setPeek] = useState<ChatMessage | null>(null); // «выглянувшее» новое сообщение в свёрнутом виде
  const lastId = useRef(0);
  const first = useRef(true);
  const list = useRef<HTMLDivElement>(null);
  const island = useRef<HTMLElement>(null);
  const openRef = useRef(open);
  openRef.current = open;

  const poll = useCallback(async () => {
    try {
      const fresh = await api.chatMessages(lastId.current);
      // Опрос и отправка могут получить одно и то же сообщение одновременно — отбрасываем уже добавленные
      const added = fresh.filter((m) => m.id > lastId.current);
      if (!added.length) return;
      lastId.current = added[added.length - 1].id;
      setMessages((m) => [...m, ...added]);
      const incoming = added.filter((m) => m.client_id !== ME);
      if (!first.current && !openRef.current && incoming.length) setPeek(incoming[incoming.length - 1]);
      first.current = false;
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
    if (!peek) return;
    const t = setTimeout(() => setPeek(null), 4000);
    return () => clearTimeout(t);
  }, [peek]);

  useEffect(() => {
    if (open && messages.length) {
      setSeen(messages[messages.length - 1].id);
      list.current?.scrollTo({ top: list.current.scrollHeight });
    }
  }, [open, messages]);

  useEffect(() => {
    if (!open) return;
    const close = (e: PointerEvent) => {
      if (!island.current?.contains(e.target as Node)) setOpen(false);
    };
    const esc = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    document.addEventListener("pointerdown", close);
    document.addEventListener("keydown", esc);
    return () => {
      document.removeEventListener("pointerdown", close);
      document.removeEventListener("keydown", esc);
    };
  }, [open]);

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

  const state = open ? "open" : peek ? "peek" : "idle";

  return (
    <section ref={island} className={`island ${state}${!open && unread > 0 ? " unread" : ""}`} aria-label="Общий чат">
      <button
        className="island-bar"
        onClick={() => {
          setPeek(null);
          setOpen(!open);
        }}
        aria-expanded={open}
      >
        <span className="island-icon">💬</span>
        {state === "peek" && peek ? (
          <span className="island-peek">
            <b>{peek.author_name}</b> {peek.text}
          </span>
        ) : (
          <span className="island-title">{open ? "Общий чат" : "Чат"}</span>
        )}
        <span className="island-online">
          <i /> {online.length}
        </span>
        {!open && unread > 0 && <span className="chat-badge">{unread}</span>}
      </button>

      <div className="island-body" aria-hidden={!open}>
        <div className="chat-online">
          {online.map((u) => (
            <span key={u.client_id} className={`chat-user${u.client_id === ME ? " me" : ""}`}>
              {u.name}
            </span>
          ))}
        </div>
        <div className="chat-list" ref={list}>
          {messages.length === 0 && <div className="chat-empty">Сообщений пока нет</div>}
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
          <input placeholder="Сообщение…" value={text} maxLength={2000} tabIndex={open ? 0 : -1} onChange={(e) => setText(e.target.value)} />
          <button type="submit" disabled={!text.trim()} tabIndex={open ? 0 : -1}>
            ➤
          </button>
        </form>
      </div>
    </section>
  );
}
