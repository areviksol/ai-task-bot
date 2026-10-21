
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models.task import Task, TaskStatus


class TaskRepository:
    def __init__(self, db: Session):
        self.db = db


    def create_from_telegram(
        self,
        task: Task,
        chat_id: int,
        message_id: int,
    ) -> tuple[Task, bool]:
        """
        Create a task once per Telegram message.

        Returns:
            (task, created)
        """
        values = {
            "id": task.id or uuid4(),
            "user_id": task.user_id,
            "title": task.title,
            "description": task.description,
            "status": task.status or TaskStatus.PENDING,
            "source": task.source,
            "telegram_chat_id": chat_id,
            "telegram_message_id": message_id,
        }

        statement = (
            insert(Task)
            .values(**values)
            .on_conflict_do_nothing(
                constraint="uq_tasks_telegram_message"
            )
            .returning(Task.id)
        )

        try:
            new_id = self.db.scalar(statement)

            self.db.commit()

            if new_id is not None:
                created_task = self.db.get(Task, new_id)
                return created_task, True

            existing_task = self.db.scalar(
                select(Task).where(
                    Task.telegram_chat_id == chat_id,
                    Task.telegram_message_id == message_id,
                    Task.user_id == task.user_id,
                )
            )

            if existing_task is None:
                raise RuntimeError(
                    "Telegram message identity conflict"
                )

            return existing_task, False

        except Exception:
            self.db.rollback()
            raise


    def create(self, task: Task) -> Task:
        try:
            self.db.add(task)
            self.db.commit()
            self.db.refresh(task)
            return task
        except Exception:
            self.db.rollback()
            raise

    def get_by_id(
        self,
        task_id: UUID,
        user_id: UUID,
    ) -> Task | None:
        stmt = select(Task).where(
            Task.id == task_id,
            Task.user_id == user_id,
        )
        return self.db.scalar(stmt)

    def get_all_by_user(
        self,
        user_id: UUID,
    ) -> list[Task]:
        stmt = (
            select(Task)
            .where(Task.user_id == user_id)
            .order_by(Task.created_at.desc())
        )
        return list(self.db.scalars(stmt).all())

    def update(self, task: Task) -> Task:
        try:
            self.db.add(task)
            self.db.commit()
            self.db.refresh(task)
            return task
        except Exception:
            self.db.rollback()
            raise

    def delete(self, task: Task) -> None:
        try:
            self.db.delete(task)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
