export type Priority = "low" | "normal" | "high" | "urgent";

export interface Author {
  id: number;
  username: string | null;
  full_name: string | null;
}

export interface Attachment {
  id: number;
  type: string;
  file_id: string | null;
  file_name: string | null;
  mime_type: string | null;
  file_size: number | null;
}

export interface Task {
  id: number;
  title: string;
  description: string;
  column_id: number;
  position: number;
  priority: Priority;
  due_at: string | null;
  source: string;
  author: Author | null;
  author_name: string | null;
  sent_at: string | null;
  edited: boolean;
  tags: string[];
  attachments: Attachment[];
  created_at: string;
  updated_at: string;
}

export interface Column {
  id: number;
  name: string;
  position: number;
  tasks: Task[];
}

export interface Board {
  columns: Column[];
}

export interface Tag {
  name: string;
  count: number;
}

export interface TaskPatch {
  title?: string;
  description?: string;
  priority?: Priority;
  due_at?: string | null;
  tags?: string[];
}

export interface TaskCreate extends TaskPatch {
  title: string;
  column_id?: number;
  author_name?: string;
}
