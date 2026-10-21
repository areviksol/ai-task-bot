
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from sqlalchemy import and_, or_, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models.task import Task, TaskSource
from app.models.voice_job import VoiceJob, VoiceJobStatus


MAX_ATTEMPTS = 5

LEASE_DURATION = timedelta(minutes=20)


class StaleVoiceLeaseError(Exception):
    """The processing attempt no longer owns the job."""


LEASE_DURATION = timedelta(minutes=20)


class StaleVoiceLeaseError(Exception):
    """The processing attempt no longer owns the job."""


class VoiceJobRepository:
    def __init__(self, db: Session):
        self.db = db

    def create_or_get(
        self,
        user_id: UUID,
        chat_id: int,
        message_id: int,
        file_id: str,
    ) -> tuple[VoiceJob, bool]:
        stmt = (
            insert(VoiceJob)
            .values(
                id=uuid4(),
                user_id=user_id,
                telegram_chat_id=chat_id,
                telegram_message_id=message_id,
                telegram_file_id=file_id,
                status=VoiceJobStatus.QUEUED,
                attempts=0,
            )
            .on_conflict_do_nothing(
                constraint="uq_voice_jobs_telegram_message"
            )
            .returning(VoiceJob.id)
        )

        try:
            new_id = self.db.scalar(stmt)

            if new_id is not None:
                job = self.db.get(VoiceJob, new_id)
                created = True
            else:
                job = self.db.scalar(
                    select(VoiceJob).where(
                        VoiceJob.telegram_chat_id == chat_id,
                        VoiceJob.telegram_message_id == message_id,
                    )
                )
                created = False

            if job is None or job.user_id != user_id:
                raise ValueError("Voice job identity conflict")

            self.db.commit()
            return job, created

        except Exception:
            self.db.rollback()
            raise

    def get_by_id(self, job_id: UUID) -> VoiceJob | None:
        return self.db.get(VoiceJob, job_id)

    
    def claim_for_processing(
        self,
        job_id: UUID,
    ) -> tuple[VoiceJob, UUID] | None:
        now = datetime.now(timezone.utc)
        token = uuid4()

        stmt = (
            update(VoiceJob)
            .where(
                VoiceJob.id == job_id,
                or_(
                    VoiceJob.status == VoiceJobStatus.QUEUED,
                    and_(
                        VoiceJob.status == VoiceJobStatus.PROCESSING,
                        VoiceJob.lease_expires_at < now,
                    ),
                ),
            )
            .values(
                status=VoiceJobStatus.PROCESSING,
                lease_token=token,
                lease_expires_at=now + LEASE_DURATION,
                attempts=VoiceJob.attempts + 1,
            )
            .returning(VoiceJob.id)
        )

        try:
            claimed_id = self.db.scalar(stmt)
            self.db.commit()

            if claimed_id is None:
                return None

            job = self.db.get(VoiceJob, claimed_id)
            return job, token

        except Exception:
            self.db.rollback()
            raise

    
    def complete_with_task(
        self,
        job_id: UUID,
        lease_token: UUID,
        transcription: str,
    ) -> Task:
        try:
            job = self.db.scalar(
                select(VoiceJob)
                .where(VoiceJob.id == job_id)
                .with_for_update()
            )

            now = datetime.now(timezone.utc)

            if (
                job is None
                or job.status != VoiceJobStatus.PROCESSING
                or job.lease_token != lease_token
                or job.lease_expires_at is None
                or job.lease_expires_at <= now
            ):
                raise StaleVoiceLeaseError(
                    "Voice job lease is no longer valid"
                )

            task = Task(
                user_id=job.user_id,
                title=transcription[:255],
                description=transcription,
                source=TaskSource.TELEGRAM_VOICE,
                telegram_chat_id=job.telegram_chat_id,
                telegram_message_id=job.telegram_message_id,
            )

            self.db.add(task)
            self.db.flush()

            job.task_id = task.id
            job.transcription = transcription
            job.status = VoiceJobStatus.COMPLETED
            job.error_message = None
            job.lease_token = None
            job.lease_expires_at = None

            self.db.commit()
            self.db.refresh(task)

            return task

        except Exception:
            self.db.rollback()
            raise

    
    def mark_failed(
        self,
        job_id: UUID,
        lease_token: UUID,
        error_message: str,
    ) -> bool:
        now = datetime.now(timezone.utc)

        stmt = (
            update(VoiceJob)
            .where(
                VoiceJob.id == job_id,
                VoiceJob.status == VoiceJobStatus.PROCESSING,
                VoiceJob.lease_token == lease_token,
                VoiceJob.lease_expires_at > now,
            )
            .values(
                status=VoiceJobStatus.FAILED,
                error_message=error_message[:1000],
                lease_token=None,
                lease_expires_at=None,
            )
            .returning(VoiceJob.id)
        )

        try:
            updated_id = self.db.scalar(stmt)
            self.db.commit()
            return updated_id is not None
        except Exception:
            self.db.rollback()
            raise


    def requeue(
        self,
        job_id: UUID,
        lease_token: UUID,
    ) -> bool:
        now = datetime.now(timezone.utc)

        stmt = (
            update(VoiceJob)
            .where(
                VoiceJob.id == job_id,
                VoiceJob.status == VoiceJobStatus.PROCESSING,
                VoiceJob.lease_token == lease_token,
                VoiceJob.lease_expires_at > now,
            )
            .values(
                status=VoiceJobStatus.QUEUED,
                lease_token=None,
                lease_expires_at=None,
            )
            .returning(VoiceJob.id)
        )

        try:
            updated_id = self.db.scalar(stmt)
            self.db.commit()
            return updated_id is not None
        except Exception:
            self.db.rollback()
            raise

    
    def find_recoverable_jobs(
        self,
        limit: int = 100,
    ) -> list[UUID]:
        now = datetime.now(timezone.utc)
        queued_before = now - timedelta(minutes=1)

        stmt = (
            select(VoiceJob.id)
            .where(
                or_(
                    and_(
                        VoiceJob.status == VoiceJobStatus.QUEUED,
                        VoiceJob.updated_at < queued_before,
                    ),
                    and_(
                        VoiceJob.status == VoiceJobStatus.PROCESSING,
                        VoiceJob.lease_expires_at < now,
                    ),
                )
            )
            .order_by(VoiceJob.created_at)
            .limit(limit)
        )

        return list(self.db.scalars(stmt))

    
    def fail_exhausted_jobs(self) -> int:
        now = datetime.now(timezone.utc)

        stmt = (
            update(VoiceJob)
            .where(
                VoiceJob.attempts >= MAX_ATTEMPTS,
                or_(
                    VoiceJob.status == VoiceJobStatus.QUEUED,
                    and_(
                        VoiceJob.status == VoiceJobStatus.PROCESSING,
                        VoiceJob.lease_expires_at < now,
                    ),
                ),
            )
            .values(
                status=VoiceJobStatus.FAILED,
                error_message="Maximum processing attempts exceeded",
                lease_token=None,
                lease_expires_at=None,
            )
        )

        try:
            result = self.db.execute(stmt)
            self.db.commit()
            return result.rowcount
        except Exception:
            self.db.rollback()
            raise


    def renew_lease(
        self,
        job_id: UUID,
        lease_token: UUID,
    ) -> bool:
        now = datetime.now(timezone.utc)

        stmt = (
            update(VoiceJob)
            .where(
                VoiceJob.id == job_id,
                VoiceJob.status == VoiceJobStatus.PROCESSING,
                VoiceJob.lease_token == lease_token,
                VoiceJob.lease_expires_at > now,
            )
            .values(
                lease_expires_at=now + LEASE_DURATION,
            )
            .returning(VoiceJob.id)
        )

        try:
            renewed_id = self.db.scalar(stmt)
            self.db.commit()
            return renewed_id is not None

        except Exception:
            self.db.rollback()
            raise
