
from typing import Annotated
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Response,
    status,
)

from app.dependencies.auth import (
    CurrentUser,
    get_current_user,
)
from app.dependencies.tasks import TaskServiceDep
from app.schemas.task import (
    TaskCreate,
    TaskResponse,
    TaskUpdate,
)
from app.services.task_service import TaskNotFoundError
from app.dependencies.auth import require_safe_origin

router = APIRouter(
    prefix="/tasks",
    tags=["Tasks"],
    dependencies=[Depends(require_safe_origin)],
)

CurrentUserDep = Annotated[
    CurrentUser,
    Depends(get_current_user),
]


@router.post(
    "",
    response_model=TaskResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_task(
    data: TaskCreate,
    service: TaskServiceDep,
    current_user: CurrentUserDep,
):
    return service.create_task(
        user_id=current_user.id,
        data=data,
    )


@router.get(
    "",
    response_model=list[TaskResponse],
)
def list_tasks(
    service: TaskServiceDep,
    current_user: CurrentUserDep,
):
    return service.list_tasks(current_user.id)


@router.get(
    "/{task_id}",
    response_model=TaskResponse,
)
def get_task(
    task_id: UUID,
    service: TaskServiceDep,
    current_user: CurrentUserDep,
):
    try:
        return service.get_task(
            task_id=task_id,
            user_id=current_user.id,
        )
    except TaskNotFoundError:
        raise HTTPException(
            status_code=404,
            detail="Task not found",
        )


@router.patch(
    "/{task_id}",
    response_model=TaskResponse,
)
def update_task(
    task_id: UUID,
    data: TaskUpdate,
    service: TaskServiceDep,
    current_user: CurrentUserDep,
):
    try:
        return service.update_task(
            task_id=task_id,
            user_id=current_user.id,
            data=data,
        )
    except TaskNotFoundError:
        raise HTTPException(
            status_code=404,
            detail="Task not found",
        )


@router.delete(
    "/{task_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_task(
    task_id: UUID,
    service: TaskServiceDep,
    current_user: CurrentUserDep,
):
    try:
        service.delete_task(
            task_id=task_id,
            user_id=current_user.id,
        )
    except TaskNotFoundError:
        raise HTTPException(
            status_code=404,
            detail="Task not found",
        )

    return Response(status_code=204)
