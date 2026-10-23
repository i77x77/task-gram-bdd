import type { Board, BoardInfo, ChatMessage, OnlineUser, Column, Tag, Task, TaskCreate, TaskPatch } from "./types";

export const BASE = import.meta.env.VITE_API_URL ?? "/api/v1";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(BASE + path, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail ?? body);
    } catch {
      /* тело не JSON */
    }
    throw new Error(detail);
  }
  return res.status === 204 ? (undefined as T) : res.json();
}

const json = (method: string, body: unknown): RequestInit => ({ method, body: JSON.stringify(body) });

export interface BoardFilter {
  q?: string;
  tag?: string;
  boardId?: number;
}

export const api = {
  boards: () => request<BoardInfo[]>("/boards"),
  board: ({ q, tag, boardId }: BoardFilter = {}) => {
    const params = new URLSearchParams();
    if (boardId) params.set("board_id", String(boardId));
    if (q) params.set("q", q);
    if (tag) params.set("tag", tag);
    const qs = params.toString();
    return request<Board>(`/board${qs ? `?${qs}` : ""}`);
  },
  chatMessages: (afterId = 0) => request<ChatMessage[]>(`/chat/messages?after_id=${afterId}`),
  sendChatMessage: (client_id: string, author_name: string, text: string) =>
    request<ChatMessage>("/chat/messages", json("POST", { client_id, author_name, text })),
  heartbeat: (client_id: string, name: string) => request<OnlineUser[]>("/chat/heartbeat", json("POST", { client_id, name })),
  tags: () => request<Tag[]>("/tags"),
  createTask: (body: TaskCreate) => request<Task>("/tasks", json("POST", body)),
  updateTask: (id: number, body: TaskPatch) => request<Task>(`/tasks/${id}`, json("PATCH", body)),
  deleteTask: (id: number) => request<void>(`/tasks/${id}`, { method: "DELETE" }),
  moveTask: (id: number, column_id: number, position: number) =>
    request<Task>(`/tasks/${id}/move`, json("POST", { column_id, position })),
  createColumn: (name: string) => request<Column>("/columns", json("POST", { name })),
  renameColumn: (id: number, name: string) => request<Column>(`/columns/${id}`, json("PATCH", { name })),
  deleteColumn: (id: number, moveTo?: number) =>
    request<void>(`/columns/${id}${moveTo ? `?move_to=${moveTo}` : ""}`, { method: "DELETE" }),
};
