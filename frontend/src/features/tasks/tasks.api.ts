
import { apiRequest } from "../../api/client";
import type { Task, TaskStatus } from "./types";

export function getTasks(): Promise<Task[]> {
  return apiRequest<Task[]>("/tasks");
}

export function updateTaskStatus(
  id: string,
  status: TaskStatus,
): Promise<Task> {
  return apiRequest<Task>(`/tasks/${id}`, {
    method: "PATCH",
    body: JSON.stringify({ status }),
  });
}

export function createTask(title: string): Promise<Task> {
  return apiRequest<Task>("/tasks", {
    method: "POST",
    body: JSON.stringify({ title }),
  });
}
