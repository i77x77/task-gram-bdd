import { useSortable } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import type { Task } from "../api/types";

const PRIORITY_LABEL = { low: "Низкий", normal: "Обычный", high: "Высокий", urgent: "Срочно" } as const;

export function dueLabel(iso: string) {
  return new Date(iso).toLocaleDateString("ru-RU", { day: "numeric", month: "short" });
}

export function TaskCardView({ task, overlay }: { task: Task; overlay?: boolean }) {
  const overdue = task.due_at !== null && new Date(task.due_at) < new Date();
  return (
    <div className={`card prio-${task.priority}${overlay ? " overlay" : ""}`}>
      <div className="card-title">{task.title}</div>
      {task.tags.length > 0 && (
        <div className="tags">
          {task.tags.map((t) => (
            <span key={t} className="tag">
              #{t}
            </span>
          ))}
        </div>
      )}
      <div className="card-meta">
        {task.priority !== "normal" && <span className={`badge prio-${task.priority}`}>{PRIORITY_LABEL[task.priority]}</span>}
        {task.due_at && <span className={`badge${overdue ? " overdue" : ""}`}>⏰ {dueLabel(task.due_at)}</span>}
        {task.attachments.length > 0 && <span className="badge">📎 {task.attachments.length}</span>}
        {task.source === "telegram" && <span className="badge">✈️ {task.author?.username ? `@${task.author.username}` : task.author?.full_name}</span>}
      </div>
    </div>
  );
}

export function TaskCard({ task, onOpen }: { task: Task; onOpen: (t: Task) => void }) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({
    id: `task-${task.id}`,
  });
  return (
    <div
      ref={setNodeRef}
      style={{ transform: CSS.Transform.toString(transform), transition, opacity: isDragging ? 0.35 : 1 }}
      onClick={() => onOpen(task)}
      {...attributes}
      {...listeners}
    >
      <TaskCardView task={task} />
    </div>
  );
}
