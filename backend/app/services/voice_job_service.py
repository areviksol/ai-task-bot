
from uuid import UUID

from app.models.voice_job import VoiceJob, VoiceJobStatus
from app.repositories.voice_job_repository import (
    VoiceJobRepository,
)


class VoiceJobNotFoundError(Exception):
    pass


class InvalidVoiceJobStateError(Exception):
    pass


class VoiceJobService:
    def __init__(
        self,
        repository: VoiceJobRepository,
    ):
        self.repository = repository

    def register_voice(
        self,
        user_id: UUID,
        chat_id: int,
        message_id: int,
        file_id: str,
    ) -> tuple[VoiceJob, bool]:
        if not file_id:
            raise ValueError("Voice file ID is required")

        return self.repository.create_or_get(
            user_id=user_id,
            chat_id=chat_id,
            message_id=message_id,
            file_id=file_id,
        )

    def start_processing(
        self,
        job_id: UUID,
    ) -> tuple[VoiceJob, UUID] | None:
        return self.repository.claim_for_processing(job_id)


    def complete_processing(
        self,
        job_id: UUID,
        lease_token: UUID,
        transcription: str,
    ):
        transcription = transcription.strip()

        if not transcription:
            raise ValueError("Transcription cannot be empty")

        return self.repository.complete_with_task(
            job_id=job_id,
            lease_token=lease_token,
            transcription=transcription,
        )
    
    def fail_processing(
        self,
        job_id: UUID,
        lease_token: UUID,
        error_message: str,
    ) -> bool:
        return self.repository.mark_failed(
            job_id=job_id,
            lease_token=lease_token,
            error_message=error_message,
        )

    def get_job(self, job_id: UUID) -> VoiceJob:
        job = self.repository.get_by_id(job_id)

        if job is None:
            raise VoiceJobNotFoundError(
                "Voice job not found"
            )

        return job
    
    def retry_processing(
        self,
        job_id: UUID,
        lease_token: UUID,
    ) -> bool:
        return self.repository.requeue(
            job_id=job_id,
            lease_token=lease_token,
        )

    def find_recoverable_jobs(
        self,
        limit: int = 100,
    ) -> list[UUID]:
        return self.repository.find_recoverable_jobs(limit)

    def fail_exhausted_jobs(self) -> int:
        return self.repository.fail_exhausted_jobs()

    
    def renew_processing_lease(
        self,
        job_id: UUID,
        lease_token: UUID,
    ) -> bool:
        return self.repository.renew_lease(
            job_id=job_id,
            lease_token=lease_token,
        )
