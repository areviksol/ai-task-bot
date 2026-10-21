
from uuid import UUID

from app.models.task import Task, TaskSource
from app.repositories.task_repository import TaskRepository
from app.schemas.task import TaskCreate, TaskUpdate


class TaskNotFoundError(Exception):
    pass


class TaskService:
    def __init__(
        self,
        repository: TaskRepository,
    ):
        self.repository = repository

    def create_task(
        self,
        user_id: UUID,
        data: TaskCreate,
        source: TaskSource = TaskSource.WEB,
    ) -> Task:
        task = Task(
            user_id=user_id,
            title=data.title,
            description=data.description,
            source=source,
        )

        return self.repository.create(task)

    def get_task(
        self,
        task_id: UUID,
        user_id: UUID,
    ) -> Task:
        task = self.repository.get_by_id(
            task_id=task_id,
            user_id=user_id,
        )

        if task is None:
            raise TaskNotFoundError("Task not found")

        return task

    def list_tasks(
        self,
        user_id: UUID,
    ) -> list[Task]:
        return self.repository.get_all_by_user(user_id)

    def update_task(
        self,
        task_id: UUID,
        user_id: UUID,
        data: TaskUpdate,
    ) -> Task:
        task = self.get_task(task_id, user_id)

        changes = data.model_dump(exclude_unset=True)

        for field, value in changes.items():
            setattr(task, field, value)

        return self.repository.update(task)

    def delete_task(
        self,
        task_id: UUID,
        user_id: UUID,
    ) -> None:
        task = self.get_task(task_id, user_id)
        self.repository.delete(task)


    def create_telegram_task(
        self,
        user_id: UUID,
        data: TaskCreate,
        source: TaskSource,
        chat_id: int,
        message_id: int,
    ) -> tuple[Task, bool]:

        if source not in {
            TaskSource.TELEGRAM_TEXT,
            TaskSource.TELEGRAM_VOICE,
        }:
            raise ValueError(
                "Invalid source for Telegram task"
            )

        task = Task(
            user_id=user_id,
            title=data.title,
            description=data.description,
            source=source,
        )

        return self.repository.create_from_telegram(
            task=task,
            chat_id=chat_id,
            message_id=message_id,
        )
