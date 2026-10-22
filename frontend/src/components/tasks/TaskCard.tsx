
import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { useDraggable } from "@dnd-kit/core";
import { CSS } from "@dnd-kit/utilities";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { deleteTask } from "../../features/tasks/tasks.api";
import type { Task } from "../../features/tasks/types";

interface Props {
  task: Task;
}

export default function TaskCard({ task }: Props) {
  const queryClient = useQueryClient();

  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [error, setError] = useState("");

  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    isDragging,
  } = useDraggable({
    id: task.id,
    disabled: showDeleteModal,
  });

  const deleteMutation = useMutation({
    mutationFn: () => deleteTask(task.id),

    onSuccess: async () => {
      setShowDeleteModal(false);

      await queryClient.invalidateQueries({
        queryKey: ["tasks"],
      });
    },

    onError: () => {
      setError("Could not delete this task. Please try again.");
    },
  });

  useEffect(() => {
    if (!showDeleteModal) return;

    const onKeyDown = (event: KeyboardEvent) => {
      if (
        event.key === "Escape" &&
        !deleteMutation.isPending
      ) {
        setShowDeleteModal(false);
      }
    };

    document.addEventListener("keydown", onKeyDown);

    return () => {
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [showDeleteModal, deleteMutation.isPending]);

  const openDeleteModal = () => {
    setError("");
    setShowDeleteModal(true);
  };

  const closeDeleteModal = () => {
    if (deleteMutation.isPending) return;
    setShowDeleteModal(false);
  };

  const style = {
    transform: CSS.Translate.toString(transform),
    opacity: isDragging ? 0.5 : 1,
  };

  return (
    <>
      <article
        ref={setNodeRef}
        className="kanban-card"
        style={style}
        {...attributes}
        {...listeners}
      >
        <div className="task-card-header">
          <h3>{task.title}</h3>

          <button
            type="button"
            className="task-delete-button"
            aria-label={`Delete task: ${task.title}`}
            title="Delete task"
            onPointerDown={(event) => {
              event.stopPropagation();
            }}
            onKeyDown={(event) => {
              event.stopPropagation();
            }}
            onClick={(event) => {
              event.stopPropagation();
              openDeleteModal();
            }}
          >
            ×
          </button>
        </div>

        {task.description && (
          <p>{task.description}</p>
        )}

        <small>
          {task.source.replaceAll("_", " ")}
        </small>
      </article>

      {showDeleteModal &&
        createPortal(
          <div
            className="delete-modal-overlay"
            onMouseDown={(event) => {
              if (event.target === event.currentTarget) {
                closeDeleteModal();
              }
            }}
          >
            <div
              className="delete-modal"
              role="alertdialog"
              aria-modal="true"
              aria-labelledby="delete-modal-title"
              aria-describedby="delete-modal-description"
            >
              <div className="delete-modal-icon">!</div>

              <h2 id="delete-modal-title">
                Delete task?
              </h2>

              <p id="delete-modal-description">
                Are you sure you want to delete{" "}
                <strong>{task.title}</strong>?
                This action cannot be undone.
              </p>

              {error && (
                <p
                  className="delete-modal-error"
                  role="alert"
                >
                  {error}
                </p>
              )}

              <div className="delete-modal-actions">
                <button
                  type="button"
                  className="delete-modal-cancel"
                  onClick={closeDeleteModal}
                  disabled={deleteMutation.isPending}
                >
                  Cancel
                </button>

                <button
                  type="button"
                  className="delete-modal-confirm"
                  onClick={() => deleteMutation.mutate()}
                  disabled={deleteMutation.isPending}
                >
                  {deleteMutation.isPending
                    ? "Deleting..."
                    : "Delete task"}
                </button>
              </div>
            </div>
          </div>,
          document.body
        )}
    </>
  );
}
