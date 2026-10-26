import type { Board, BoardInfo, ChatMessage, Note, OnlineUser, Column, Tag, Task, TaskCreate, TaskPatch } from "./types";

export const BASE = import.meta.env.VITE_API_URL ?? "/api/v1";

const PASSWORD_KEY = "appPassword";

export const getPassword = (): string => {
  try {
    return localStorage.getItem(PASSWORD_KEY) ?? "";
  } catch {
    return "";
  }
};

/** Админ-режим включается вручную: localStorage.setItem("isAdmin", "true"). Это только скрытие кнопок в UI, не защита API. */
export const isAdmin = (): boolean => {
  try {
    return localStorage.getItem("isAdmin") === "true";
  } catch {
    return false;
  }
};

export const setPassword = (value: string) => {
  try {
    if (value) localStorage.setItem(PASSWORD_KEY, value);
    else localStorage.removeItem(PASSWORD_KEY);
  } catch {
    /* без хранилища придётся вводить пароль при каждой загрузке */
  }
  memoryPassword = value;
};

let memoryPassword = getPassword();

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(BASE + path, {
    ...init,
    headers: { "Content-Type": "application/json", "X-App-Password": memoryPassword, ...init?.headers },
  });
  if (res.status === 401) {
    window.dispatchEvent(new Event("auth-required"));
    throw new Error("Требуется пароль");
  }
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
  checkAuth: () => request<{ ok: boolean }>("/auth/check"),
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
  notes: () => request<Note[]>("/notes"),
  createNote: (title: string, text: string, author_name?: string) =>
    request<Note>("/notes", json("POST", { title, text, author_name })),
  updateNote: (id: number, patch: { title?: string; text?: string }) => request<Note>(`/notes/${id}`, json("PATCH", patch)),
  deleteNote: (id: number) => request<void>(`/notes/${id}`, { method: "DELETE" }),
  sheetStatus: () => request<{ enabled: boolean }>("/sheet"),
  syncSheet: () => request<{ created: number; archived: number }>("/sheet/sync", { method: "POST" }),
  iceServers: () => request<{ iceServers: RTCIceServer[] }>("/call/ice"),
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
