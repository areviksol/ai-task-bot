
import { useDraggable } from "@dnd-kit/core";
import { CSS } from "@dnd-kit/utilities";

import type { Task } from "../../features/tasks/types";

interface Props {
  task: Task;
}

export default function TaskCard({ task }: Props) {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    isDragging,
  } = useDraggable({
    id: task.id,
  });

  const style = {
    transform: CSS.Translate.toString(transform),
    opacity: isDragging ? 0.5 : 1,
  };

  return (
    <article
      ref={setNodeRef}
      className="kanban-card"
      style={style}
      {...listeners}
      {...attributes}
    >
      <h3>{task.title}</h3>

      {task.description && (
        <p>{task.description}</p>
      )}

      <small>{task.source.replaceAll("_", " ")}</small>
    </article>
  );
}
