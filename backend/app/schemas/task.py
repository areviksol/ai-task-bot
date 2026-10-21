
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.task import TaskSource, TaskStatus


class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str | None = None


class TaskUpdate(BaseModel):
    title: str | None = Field(
        default=None,
        min_length=1,
        max_length=255,
    )
    description: str | None = None
    status: TaskStatus | None = None

    @model_validator(mode="after")
    def validate_update(self):
        fields = self.model_fields_set

        if "title" in fields and self.title is None:
            raise ValueError("Title cannot be null")

        if "status" in fields and self.status is None:
            raise ValueError("Status cannot be null")

        return self


class TaskResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    title: str
    description: str | None
    status: TaskStatus
    source: TaskSource
    created_at: datetime
    updated_at: datetime
