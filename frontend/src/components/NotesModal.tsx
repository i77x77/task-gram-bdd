import { Fragment, useEffect, useState } from "react";
import { api } from "../api/client";
import type { Note } from "../api/types";

const URL_RE = /(https?:\/\/[^\s<>"']+)/g;

/** Текст заметки с кликабельными ссылками (без dangerouslySetInnerHTML). */
function Linkified({ text }: { text: string }) {
  return (
    <>
      {text.split(URL_RE).map((part, i) =>
        i % 2 ? (
          <a key={i} href={part} target="_blank" rel="noopener noreferrer">
            {part}
          </a>
        ) : (
          <Fragment key={i}>{part}</Fragment>
        ),
      )}
    </>
  );
}

const preview = (n: Note) => n.title || n.text.split("\n")[0] || "Без названия";

export function NotesModal({ userName, onClose }: { userName: string; onClose: () => void }) {
  const [notes, setNotes] = useState<Note[]>([]);
  const [selected, setSelected] = useState<number | null>(null);
  const [editing, setEditing] = useState(false);
  const [title, setTitle] = useState("");
  const [text, setText] = useState("");
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    try {
      setNotes(await api.notes());
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  useEffect(() => {
    void load();
  }, []);

  useEffect(() => {
    const esc = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    document.addEventListener("keydown", esc);
    return () => document.removeEventListener("keydown", esc);
  }, [onClose]);

  const note = notes.find((n) => n.id === selected);

  const select = (n: Note) => {
    setSelected(n.id);
    setEditing(false);
  };

  const startEdit = (n: Note) => {
    setTitle(n.title);
    setText(n.text);
    setEditing(true);
  };

  const create = async () => {
    try {
      const n = await api.createNote("", "", userName || undefined);
      setNotes((l) => [n, ...l]);
      setSelected(n.id);
      startEdit(n);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  const save = async () => {
    if (!note) return;
    try {
      const n = await api.updateNote(note.id, { title, text });
      setNotes((l) => [n, ...l.filter((x) => x.id !== n.id)]);
      setEditing(false);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  const remove = async () => {
    if (!note || !confirm("Удалить заметку?")) return;
    try {
      await api.deleteNote(note.id);
      setNotes((l) => l.filter((x) => x.id !== note.id));
      setSelected(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  return (
    <div className="backdrop" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className="modal notes" role="dialog" aria-modal aria-label="Заметки">
        <div className="notes-head">
          <span className="modal-title">📝 Заметки</span>
          <span className="spacer" />
          <button className="primary" onClick={create}>
            + Новая
          </button>
          <button onClick={onClose} aria-label="Закрыть">
            ✕
          </button>
        </div>
        {error && (
          <div className="call-error" onClick={() => setError(null)}>
            {error}
          </div>
        )}
        <div className="notes-body">
          <div className="notes-list">
            {notes.length === 0 && <div className="chat-empty">Заметок пока нет</div>}
            {notes.map((n) => (
              <button key={n.id} className={n.id === selected ? "active" : ""} onClick={() => select(n)}>
                {preview(n)}
              </button>
            ))}
          </div>
          <div className="notes-view">
            {!note ? (
              <div className="chat-empty">Выберите заметку или создайте новую</div>
            ) : editing ? (
              <>
                <input className="modal-title" placeholder="Название" value={title} maxLength={200} onChange={(e) => setTitle(e.target.value)} />
                <textarea rows={12} placeholder="Текст, ссылки…" value={text} onChange={(e) => setText(e.target.value)} autoFocus />
                <div className="actions">
                  <button className="primary" onClick={save}>
                    Сохранить
                  </button>
                  <button onClick={() => setEditing(false)}>Отмена</button>
                </div>
              </>
            ) : (
              <>
                <div className="modal-title">{note.title || "Без названия"}</div>
                <div className="note-text">
                  <Linkified text={note.text} />
                </div>
                <div className="muted">
                  {note.author_name && `${note.author_name} · `}
                  {new Date(note.updated_at).toLocaleString("ru-RU", { dateStyle: "short", timeStyle: "short" })}
                </div>
                <div className="actions">
                  <button onClick={() => startEdit(note)}>Редактировать</button>
                  <button className="danger" onClick={remove}>
                    Удалить
                  </button>
                </div>
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
