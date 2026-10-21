
import logging
import threading
from uuid import UUID

from app.db.session import SessionLocal
from app.repositories.voice_job_repository import VoiceJobRepository
from app.services.voice_job_service import VoiceJobService


logger = logging.getLogger(__name__)

HEARTBEAT_INTERVAL_SECONDS = 60


class VoiceLeaseHeartbeat:
    def __init__(self, job_id: UUID, lease_token: UUID):
        self.job_id = job_id
        self.lease_token = lease_token
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self.lease_lost = False

    def _run(self) -> None:
        while not self._stop_event.wait(
            HEARTBEAT_INTERVAL_SECONDS
        ):
            try:
                # Separate session for the heartbeat thread.
                with SessionLocal() as db:
                    service = VoiceJobService(
                        VoiceJobRepository(db)
                    )

                    renewed = service.renew_processing_lease(
                        self.job_id,
                        self.lease_token,
                    )

                if not renewed:
                    self.lease_lost = True
                    logger.warning(
                        "Lost lease for voice job %s",
                        self.job_id,
                    )
                    return

            except Exception:
                logger.exception(
                    "Lease heartbeat failed for job %s",
                    self.job_id,
                )
                # A transient DB error does not necessarily
                # mean ownership was lost. Completion still
                # requires a valid lease.

    def start(self) -> None:
        self._thread = threading.Thread(
            target=self._run,
            name=f"voice-lease-{self.job_id}",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()

        if self._thread is not None:
            self._thread.join()
