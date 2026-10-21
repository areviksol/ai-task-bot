
import {
  DndContext,
  closestCenter,
  type DragEndEvent,
} from "@dnd-kit/core";

import KanbanColumn from "./KanbanColumn";
import type {
  Task,
  TaskStatus,
} from "../../features/tasks/types";

interface Props {
  tasks: Task[];
  onStatusChange: (id: string, status: TaskStatus) => void;
  disabled?: boolean;
}

const columns: {
  title: string;
  status: TaskStatus;
}[] = [
  { title: "Pending", status: "pending" },
  { title: "In Progress", status: "in_progress" },
  { title: "Completed", status: "completed" },
];

export default function KanbanBoard({
  tasks,
  onStatusChange,
  disabled = false,
}: Props) {
  function handleDragEnd(event: DragEndEvent) {
    const { active, over } = event;

    if (!over || disabled) return;

    const task = tasks.find(
      (item) => item.id === active.id,
    );

    const targetStatus = columns.find(
      (column) => column.status === over.id,
    )?.status;

    if (
      !task ||
      !targetStatus ||
      task.status === targetStatus
    ) {
      return;
    }

    onStatusChange(task.id, targetStatus);
  }

  return (
    <DndContext
      collisionDetection={closestCenter}
      onDragEnd={handleDragEnd}
    >
      <div className="kanban-board">
        {columns.map((column) => (
          <KanbanColumn
            key={column.status}
            title={column.title}
            status={column.status}
            tasks={tasks.filter(
              (task) => task.status === column.status,
            )}
          />
        ))}
      </div>
    </DndContext>
  );
}
