
import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.task import Task
    from app.models.user import User


class VoiceJobStatus(str, enum.Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class VoiceJob(Base):
    __tablename__ = "voice_jobs"

    __table_args__ = (
        UniqueConstraint(
            "telegram_chat_id",
            "telegram_message_id",
            name="uq_voice_jobs_telegram_message",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    task_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("tasks.id", ondelete="SET NULL"),
        nullable=True,
        unique=True,
    )

    telegram_chat_id: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
    )

    telegram_message_id: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
    )

    telegram_file_id: Mapped[str] = mapped_column(
        String(512),
        nullable=False,
    )

    status: Mapped[VoiceJobStatus] = mapped_column(
        Enum(
            VoiceJobStatus,
            name="voice_job_status",
            values_callable=lambda enum_cls: [
                member.value for member in enum_cls
            ],
        ),
        default=VoiceJobStatus.QUEUED,
        server_default=VoiceJobStatus.QUEUED.value,
        nullable=False,
    )

    attempts: Mapped[int] = mapped_column(
        Integer,
        default=0,
        server_default="0",
        nullable=False,
    )

    transcription: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    lease_token: Mapped[uuid.UUID | None] = mapped_column(
        nullable=True,
    )

    lease_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    
    user: Mapped["User"] = relationship()

    task: Mapped["Task | None"] = relationship()
