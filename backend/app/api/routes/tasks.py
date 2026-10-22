
from typing import Annotated
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Response,
    status,
    File, 
    UploadFile
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
from openai import OpenAIError, RateLimitError


import logging

from app.core.config import get_settings
from app.services.transcription_service import (
    TranscriptionError,
    TranscriptionService,
)
from app.services.task_events import publish_task_changed
router = APIRouter(
    prefix="/tasks",
    tags=["Tasks"],
    dependencies=[Depends(require_safe_origin)],
)

CurrentUserDep = Annotated[
    CurrentUser,
    Depends(get_current_user),
]


logger = logging.getLogger(__name__)

ALLOWED_AUDIO_FORMATS = {
    ".webm",
    ".ogg",
    ".m4a",
    ".mp4",
    ".mp3",
    ".mpeg",
    ".mpga",
    ".wav",
}


@router.post(
    "/voice",
    response_model=TaskResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_voice_task(
    service: TaskServiceDep,
    current_user: CurrentUserDep,
    file: UploadFile = File(...),
):
    # Browser uploads must use a supported audio extension.
    filename = file.filename or "recording.webm"
    extension = "." + filename.rsplit(".", 1)[-1].lower()

    if extension not in ALLOWED_AUDIO_FORMATS:
        raise HTTPException(
            status_code=415,
            detail="Unsupported audio format",
        )

    # Read at most 20 MB + 1 byte to reject oversized uploads.
    max_bytes = TranscriptionService.MAX_AUDIO_BYTES

    try:
        audio = file.file.read(max_bytes + 1)
    finally:
        file.file.close()

    if not audio:
        raise HTTPException(
            status_code=400,
            detail="Audio recording is empty",
        )

    if len(audio) > max_bytes:
        raise HTTPException(
            status_code=413,
            detail="Audio recording is too large",
        )

    try:
        transcription = (
            TranscriptionService().transcribe_audio(
                audio=audio,
                filename=f"recording{extension}",
            )
        )
    except TranscriptionError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc

    except RateLimitError as exc:
        logger.warning(
            "Voice transcription rate limit or quota error"
        )
        raise HTTPException(
            status_code=503,
            detail="Voice transcription is temporarily unavailable",
        ) from exc

    except OpenAIError as exc:
        logger.exception("Voice transcription API failure")
        raise HTTPException(
            status_code=502,
            detail="Unable to transcribe audio",
        ) from exc

    # Task titles are limited to 255 characters.
    if len(transcription) > 255:
        raise HTTPException(
            status_code=422,
            detail="Recording is too long for a task title",
        )

    # Reuse the existing authenticated task service.
    task = service.create_task(
        user_id=current_user.id,
        data=TaskCreate(title=transcription),
    )

    # Task creation has already committed.
    # A notification failure must not undo it.
    try:
        publish_task_changed(
            user_id=current_user.id,
            redis_url=get_settings().redis_url,
        )
    except Exception:
        logger.exception(
            "Could not publish voice task event"
        )

    return task


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


