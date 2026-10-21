
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { useState } from "react";

import { ApiError } from "../api/client";
import { getCurrentUser, logout } from "../features/auth/auth.api";
import {
  createTask,
  getTasks,
  updateTaskStatus,
} from "../features/tasks/tasks.api";
import type { TaskStatus } from "../features/tasks/types";
import KanbanBoard from "../components/tasks/KanbanBoard";
import { useTaskEvents } from "../features/tasks/useTaskEvents";

export default function DashboardPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [title, setTitle] = useState("");

  const userQuery = useQuery({
    queryKey: ["currentUser"],
    queryFn: getCurrentUser,
    retry: false,
  });

  useTaskEvents(userQuery.isSuccess);

  const tasksQuery = useQuery({
    queryKey: ["tasks"],
    queryFn: getTasks,
    enabled: userQuery.isSuccess,
  });

  const createMutation = useMutation({
    mutationFn: createTask,
    onSuccess: () => {
      setTitle("");
      queryClient.invalidateQueries({ queryKey: ["tasks"] });
    },
  });

  const statusMutation = useMutation({
    mutationFn: ({
        id,
        status,
    }: {
        id: string;
        status: TaskStatus;
    }) => updateTaskStatus(id, status),
    onSuccess: () => {
        queryClient.invalidateQueries({
        queryKey: ["tasks"],
        });
    },
    });

  if (userQuery.isPending) {
    return <main className="page-message">Loading session...</main>;
  }

  if (userQuery.isError) {
    return (
      <main className="page-message">
        <h2>
          {userQuery.error instanceof ApiError &&
          userQuery.error.status === 401
            ? "Not authenticated"
            : "Unable to verify your session"}
        </h2>
        <p>Open Telegram and send /login to get a login link.</p>
        <button onClick={() => navigate("/login")}>
          Go to login
        </button>
      </main>
    );
  }

  async function handleLogout() {
    try {
      await logout();
      queryClient.clear();
      navigate("/login", { replace: true });
    } catch {
      alert("Unable to log out. Please try again.");
    }
  }

  return (
    <main className="dashboard">
      <header className="dashboard-header">
        <div>
          <h1>My Tasks</h1>
          <p>Manage tasks from Telegram and the web.</p>
        </div>
        <button className="secondary-button" onClick={handleLogout}>
          Log out
        </button>
      </header>

      <form
        className="task-form"
        onSubmit={(event) => {
          event.preventDefault();
          if (title.trim()) {
            createMutation.mutate(title.trim());
          }
        }}
      >
        <input
          type="text"
          value={title}
          maxLength={255}
          onChange={(event) => setTitle(event.target.value)}
          placeholder="Add a new task..."
          aria-label="Task title"
        />
        <button
          type="submit"
          disabled={!title.trim() || createMutation.isPending}
        >
          Add task
        </button>
      </form>

      {createMutation.isError && (
        <p className="error">Could not create task.</p>
      )}

      {statusMutation.isError && (
        <p className="error">Could not update task status.</p>
      )}

      {tasksQuery.isPending && <p>Loading tasks...</p>}
      {tasksQuery.isError && <p className="error">Could not load tasks.</p>}

      
    {tasksQuery.isSuccess && (
    <KanbanBoard
        tasks={tasksQuery.data}
        disabled={statusMutation.isPending}
        onStatusChange={(id, status) => {
        statusMutation.mutate({ id, status });
        }}
    />
    )}

    </main>
  );
}





