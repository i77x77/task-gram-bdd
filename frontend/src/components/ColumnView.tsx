import { useDroppable } from "@dnd-kit/core";
import { SortableContext, verticalListSortingStrategy } from "@dnd-kit/sortable";
import { useState } from "react";
import type { Column, Task } from "../api/types";
import { TaskCard } from "./TaskCard";

interface Props {
  column: Column;
  onOpen: (t: Task) => void;
  onAdd: (columnId: number, title: string) => Promise<void>;
  onRename: (columnId: number, name: string) => void;
}

export function ColumnView({ column, onOpen, onAdd, onRename }: Props) {
  const { setNodeRef, isOver } = useDroppable({ id: `col-${column.id}` });
  const [adding, setAdding] = useState(false);
  const [title, setTitle] = useState("");

  const submit = async () => {
    const t = title.trim();
    if (t) await onAdd(column.id, t);
    setTitle("");
    setAdding(false);
  };

  return (
    <section className={`column${isOver ? " over" : ""}`}>
      <header className="column-head">
        <input
          className="column-name"
          defaultValue={column.name}
          key={column.name}
          onBlur={(e) => {
            const name = e.target.value.trim();
            if (name && name !== column.name) onRename(column.id, name);
            else e.target.value = column.name;
          }}
          onKeyDown={(e) => e.key === "Enter" && e.currentTarget.blur()}
        />
        <button className="add-circle" title="Добавить задачу" aria-label="Добавить задачу" onClick={() => setAdding(true)}>
          +
        </button>
      </header>

      {adding && (
        <div className="add-form">
          <textarea
            autoFocus
            placeholder="Заголовок задачи"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                void submit();
              }
              if (e.key === "Escape") setAdding(false);
            }}
            onBlur={() => void submit()}
          />
        </div>
      )}

      <div ref={setNodeRef} className="column-body">
        <SortableContext items={column.tasks.map((t) => `task-${t.id}`)} strategy={verticalListSortingStrategy}>
          {column.tasks.map((t) => (
            <TaskCard key={t.id} task={t} onOpen={onOpen} />
          ))}
        </SortableContext>
      </div>

    </section>
  );
}
