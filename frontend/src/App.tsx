import {
  DndContext,
  DragOverlay,
  PointerSensor,
  closestCorners,
  useSensor,
  useSensors,
  type DragEndEvent,
  type DragOverEvent,
  type DragStartEvent,
} from "@dnd-kit/core";
import { arrayMove } from "@dnd-kit/sortable";
import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "./api/client";
import type { BoardInfo, Column, Tag, Task, TaskPatch } from "./api/types";
import { BackgroundPicker } from "./components/BackgroundPicker";
import { ChatPanel } from "./components/ChatPanel";
import { NotesModal } from "./components/NotesModal";
import { Logo } from "./components/Logo";
import { ColumnView } from "./components/ColumnView";
import { ThemeToggle } from "./components/ThemeToggle";
import { TaskCardView } from "./components/TaskCard";
import { TaskModal } from "./components/TaskModal";

const POLL_MS = 10_000;

const taskId = (id: string | number) => Number(String(id).replace("task-", ""));

/** Колонка, к которой относится dnd-id: либо сама колонка, либо та, где лежит задача. */
function findColumn(columns: Column[], id: string | number): Column | undefined {
  const s = String(id);
  if (s.startsWith("col-")) return columns.find((c) => c.id === Number(s.slice(4)));
  return columns.find((c) => c.tasks.some((t) => t.id === taskId(s)));
}

export default function App() {
  const [columns, setColumns] = useState<Column[]>([]);
  const [tags, setTags] = useState<Tag[]>([]);
  const [q, setQ] = useState("");
  const [tag, setTag] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [dragged, setDragged] = useState<Task | null>(null);
  const [notesOpen, setNotesOpen] = useState(false);
  const [openId, setOpenId] = useState<number | null>(null);
  const [userName, setUserName] = useState(() => {
    try {
      return localStorage.getItem("userName") ?? "";
    } catch {
      return "";
    }
  });
  const [boards, setBoards] = useState<BoardInfo[]>([]);
  const [boardId, setBoardId] = useState<number | null>(() => {
    try {
      return Number(localStorage.getItem("boardId")) || null;
    } catch {
      return null;
    }
  });
  const dragging = useRef(false);

  const selectBoard = (id: number) => {
    if (id === boardId) return;
    setBoardId(id);
    setColumns([]);
    setLoading(true);
    try {
      localStorage.setItem("boardId", String(id));
    } catch {
      /* localStorage недоступен */
    }
  };

  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 6 } }));

  const refresh = useCallback(async () => {
    try {
      const list = await api.boards();
      setBoards(list);
      const current = list.find((b) => b.id === boardId) ?? list[0];
      if (!current) return;
      const [board, tagList] = await Promise.all([api.board({ q: q.trim(), tag, boardId: current.id }), api.tags()]);
      if (!dragging.current) setColumns(board.columns);
      setTags(tagList);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [q, tag, boardId]);

  // Поиск с дебаунсом + периодический опрос: новые задачи из Telegram появляются сами.
  useEffect(() => {
    const t = setTimeout(refresh, 250);
    const i = setInterval(refresh, POLL_MS);
    return () => {
      clearTimeout(t);
      clearInterval(i);
    };
  }, [refresh]);

  const run = async (fn: () => Promise<unknown>) => {
    try {
      await fn();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
    await refresh();
  };

  const openTask = openId === null ? undefined : columns.flatMap((c) => c.tasks).find((t) => t.id === openId);

  // ---------- drag and drop ----------

  const onDragStart = (e: DragStartEvent) => {
    dragging.current = true;
    setDragged(columns.flatMap((c) => c.tasks).find((t) => t.id === taskId(e.active.id)) ?? null);
  };

  const onDragOver = ({ active, over }: DragOverEvent) => {
    if (!over) return;
    setColumns((cols) => {
      const from = findColumn(cols, active.id);
      const to = findColumn(cols, over.id);
      if (!from || !to || from.id === to.id) return cols;
      const task = from.tasks.find((t) => t.id === taskId(active.id))!;
      const overIndex = to.tasks.findIndex((t) => t.id === taskId(over.id));
      const index = overIndex >= 0 ? overIndex : to.tasks.length;
      return cols.map((c) => {
        if (c.id === from.id) return { ...c, tasks: c.tasks.filter((t) => t.id !== task.id) };
        if (c.id === to.id) {
          const tasks = [...c.tasks];
          tasks.splice(index, 0, { ...task, column_id: to.id });
          return { ...c, tasks };
        }
        return c;
      });
    });
  };

  const onDragEnd = async ({ active, over }: DragEndEvent) => {
    setDragged(null);
    let cols = columns;
    const col = over ? findColumn(columns, active.id) : undefined;
    if (over && col) {
      const id = taskId(active.id);
      const oldIndex = col.tasks.findIndex((t) => t.id === id);
      const overIndex = col.tasks.findIndex((t) => t.id === taskId(over.id));
      const newIndex = overIndex >= 0 ? overIndex : oldIndex;
      if (newIndex !== oldIndex) {
        cols = columns.map((c) => (c.id === col.id ? { ...c, tasks: arrayMove(c.tasks, oldIndex, newIndex) } : c));
        setColumns(cols);
      }
      const final = cols.find((c) => c.id === col.id)!;
      try {
        await api.moveTask(id, final.id, final.tasks.findIndex((t) => t.id === id));
      } catch (e) {
        setError(e instanceof Error ? e.message : String(e));
      }
    }
    dragging.current = false;
    await refresh();
  };

  const onDragCancel = () => {
    setDragged(null);
    dragging.current = false;
    void refresh();
  };

  // ---------- действия ----------

  return (
    <div className="app">
      <header className="topbar">
        <Logo />
        <input className="search" placeholder="Поиск…" value={q} onChange={(e) => setQ(e.target.value)} />
        <select value={tag} onChange={(e) => setTag(e.target.value)}>
          <option value="">Все теги</option>
          {tags.map((t) => (
            <option key={t.name} value={t.name}>
              #{t.name} ({t.count})
            </option>
          ))}
        </select>
        <span className="spacer" />
        <input
          className="user-name"
          placeholder="Ваше имя"
          value={userName}
          maxLength={100}
          onChange={(e) => {
            setUserName(e.target.value);
            try {
              localStorage.setItem("userName", e.target.value);
            } catch {
              /* localStorage недоступен */
            }
          }}
        />
        <button onClick={() => setNotesOpen(true)}>📝 Заметки</button>
        <BackgroundPicker />
        <ThemeToggle />
      </header>

      {boards.length > 0 && (
        <nav className="board-tabs seg" aria-label="Проекты">
          {boards.map((b) => (
            <button
              key={b.id}
              className={b.id === (boards.find((x) => x.id === boardId) ?? boards[0]).id ? "active" : ""}
              onClick={() => selectBoard(b.id)}
            >
              {b.name}
            </button>
          ))}
        </nav>
      )}

      {error && (
        <div className="error" onClick={() => setError(null)}>
          {error} <small>(нажмите, чтобы скрыть)</small>
        </div>
      )}

      {loading ? (
        <div className="empty">Загрузка…</div>
      ) : (
        <DndContext
          sensors={sensors}
          collisionDetection={closestCorners}
          onDragStart={onDragStart}
          onDragOver={onDragOver}
          onDragEnd={onDragEnd}
          onDragCancel={onDragCancel}
        >
          <main className="board">
            {columns.map((c) => (
              <ColumnView
                key={c.id}
                column={c}
                onOpen={(t) => setOpenId(t.id)}
                onAdd={(columnId, title) => run(() => api.createTask({ title, column_id: columnId, author_name: userName || undefined }))}
                onRename={(id, name) => run(() => api.renameColumn(id, name))}
                onDelete={(col) => {
                  const n = col.tasks.length;
                  const msg = n ? `Удалить колонку «${col.name}» вместе с задачами (${n})?` : `Удалить колонку «${col.name}»?`;
                  if (!confirm(msg)) return;
                  void run(async () => {
                    await Promise.all(col.tasks.map((t) => api.deleteTask(t.id)));
                    await api.deleteColumn(col.id);
                  });
                }}
              />
            ))}
          </main>
          <DragOverlay>{dragged && <TaskCardView task={dragged} overlay />}</DragOverlay>
        </DndContext>
      )}

      {notesOpen && <NotesModal userName={userName.trim()} onClose={() => setNotesOpen(false)} />}

      <ChatPanel userName={userName.trim()} />

      {openTask && (
        <TaskModal
          key={openTask.id}
          task={openTask}
          onClose={() => setOpenId(null)}
          onSave={(id: number, patch: TaskPatch) => run(() => api.updateTask(id, patch))}
          onDelete={(id) => run(() => api.deleteTask(id))}
        />
      )}
    </div>
  );
}
