
from unittest.mock import Mock, patch
from uuid import uuid4

from app.workers.lease_heartbeat import VoiceLeaseHeartbeat


def test_heartbeat_starts_and_stops():
    heartbeat = VoiceLeaseHeartbeat(
        job_id=uuid4(),
        lease_token=uuid4(),
    )

    heartbeat.start()
    heartbeat.stop()

    assert heartbeat._thread is not None
    assert not heartbeat._thread.is_alive()


def test_heartbeat_initially_owns_lease():
    heartbeat = VoiceLeaseHeartbeat(
        job_id=uuid4(),
        lease_token=uuid4(),
    )

    assert heartbeat.lease_lost is False


def test_heartbeat_detects_lost_lease():
    heartbeat = VoiceLeaseHeartbeat(
        job_id=uuid4(),
        lease_token=uuid4(),
    )

    with (
        patch(
            "app.workers.lease_heartbeat.SessionLocal"
        ) as session_factory,
        patch(
            "app.workers.lease_heartbeat."
            "HEARTBEAT_INTERVAL_SECONDS",
            0.01,
        ),
        patch(
            "app.workers.lease_heartbeat."
            "VoiceJobService"
        ) as service_class,
    ):
        session_factory.return_value.__enter__.return_value = Mock()
        service_class.return_value.renew_processing_lease.return_value = False

        heartbeat.start()

        assert heartbeat._thread is not None
        heartbeat._thread.join(timeout=2)

        heartbeat.stop()

    assert heartbeat.lease_lost is True
