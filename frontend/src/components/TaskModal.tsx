import { useState } from "react";
import type { Priority, Task, TaskPatch } from "../api/types";

interface Props {
  task: Task;
  onSave: (id: number, patch: TaskPatch) => Promise<void>;
  onDelete: (id: number) => Promise<void>;
  onClose: () => void;
}

const toLocalInput = (iso: string | null) => {
  if (!iso) return "";
  const d = new Date(iso);
  d.setMinutes(d.getMinutes() - d.getTimezoneOffset());
  return d.toISOString().slice(0, 16);
};

export function TaskModal({ task, onSave, onDelete, onClose }: Props) {
  const [title, setTitle] = useState(task.title);
  const [description, setDescription] = useState(task.description);
  const [priority, setPriority] = useState<Priority>(task.priority);
  const [due, setDue] = useState(toLocalInput(task.due_at));
  const [tags, setTags] = useState(task.tags.join(", "));
  const [busy, setBusy] = useState(false);

  const save = async () => {
    if (!title.trim()) return;
    setBusy(true);
    try {
      await onSave(task.id, {
        title: title.trim(),
        description,
        priority,
        due_at: due ? new Date(due).toISOString() : null,
        tags: tags.split(/[,\s]+/).map((t) => t.replace(/^#/, "")).filter(Boolean),
      });
      onClose();
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="backdrop" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className="modal" role="dialog" aria-modal>
        <input className="modal-title" value={title} onChange={(e) => setTitle(e.target.value)} />

        <label>
          Описание
          <textarea rows={6} value={description} onChange={(e) => setDescription(e.target.value)} />
        </label>

        <div className="row">
          <label>
            Приоритет
            <select value={priority} onChange={(e) => setPriority(e.target.value as Priority)}>
              <option value="low">Низкий</option>
              <option value="normal">Обычный</option>
              <option value="high">Высокий</option>
              <option value="urgent">Срочно</option>
            </select>
          </label>
          <label>
            Дедлайн
            <input type="datetime-local" value={due} onChange={(e) => setDue(e.target.value)} />
          </label>
        </div>

        <label>
          Теги (через запятую)
          <input value={tags} onChange={(e) => setTags(e.target.value)} placeholder="bug, backend" />
        </label>

        {task.attachments.length > 0 && (
          <div className="attachments">
            {task.attachments.map((a) => (
              <span key={a.id} className="badge">
                📎 {a.file_name ?? a.type}
              </span>
            ))}
          </div>
        )}

        <div className="muted">
          {task.source === "telegram" && task.author && (
            <>
              Из Telegram: {task.author.full_name ?? task.author.username}
              {task.edited && " (изменено)"} ·{" "}
            </>
          )}
          {task.source !== "telegram" && task.author_name && <>{task.author_name} · </>}
          создана {new Date(task.created_at).toLocaleString("ru-RU")}
        </div>

        <div className="actions">
          <button
            className="danger"
            onClick={async () => {
              if (confirm("Удалить задачу?")) {
                await onDelete(task.id);
                onClose();
              }
            }}
          >
            Удалить
          </button>
          <span className="spacer" />
          <button onClick={onClose}>Отмена</button>
          <button className="primary" disabled={busy} onClick={save}>
            Сохранить
          </button>
        </div>
      </div>
    </div>
  );
}
