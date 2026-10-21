
export type TaskStatus =
  | "pending"
  | "in_progress"
  | "completed";

export type TaskSource =
  | "web"
  | "telegram_text"
  | "telegram_voice";

export interface Task {
  id: string;
  user_id: string;
  title: string;
  description: string | null;
  status: TaskStatus;
  source: TaskSource;
  created_at: string;
  updated_at: string;
}
