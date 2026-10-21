
import { useDroppable } from "@dnd-kit/core";

import TaskCard from "./TaskCard";
import type {
  Task,
  TaskStatus,
} from "../../features/tasks/types";

interface Props {
  title: string;
  status: TaskStatus;
  tasks: Task[];
}

export default function KanbanColumn({
  title,
  status,
  tasks,
}: Props) {
  const { isOver, setNodeRef } = useDroppable({
    id: status,
  });

  return (
    <section
      ref={setNodeRef}
      className={`kanban-column ${isOver ? "is-over" : ""}`}
    >
      <header className="column-header">
        <h2>{title}</h2>
        <span className="task-count">{tasks.length}</span>
      </header>

      <div className="column-tasks">
        {tasks.map((task) => (
          <TaskCard key={task.id} task={task} />
        ))}

        {tasks.length === 0 && (
          <p className="empty-column">Drop a task here</p>
        )}
      </div>
    </section>
  );
}
