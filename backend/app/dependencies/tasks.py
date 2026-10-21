
from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.repositories.task_repository import TaskRepository
from app.services.task_service import TaskService


def get_task_repository(
    db: Annotated[Session, Depends(get_db)],
) -> TaskRepository:
    return TaskRepository(db)


def get_task_service(
    repository: Annotated[
        TaskRepository,
        Depends(get_task_repository),
    ],
) -> TaskService:
    return TaskService(repository)


TaskServiceDep = Annotated[
    TaskService,
    Depends(get_task_service),
]
