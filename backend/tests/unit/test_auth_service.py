
from uuid import uuid4

import pytest

from app.services.auth_service import (
    AuthService,
    InvalidLoginTokenError,
)


class FakeAuthRepository:
    def __init__(self):
        self.tokens = {}
        self.sessions = {}

    def create_login_token(
        self, user_id, token_hash, expires_at
    ):
        self.tokens[token_hash] = {
            "user_id": user_id,
            "used": False,
        }

    def redeem_login_token(
        self, token_hash, session_hash, session_expires_at
    ):
        record = self.tokens.get(token_hash)

        if record is None or record["used"]:
            return None

        record["used"] = True
        self.sessions[session_hash] = record["user_id"]

        return record["user_id"]

    def get_session_user_id(self, session_hash):
        return self.sessions.get(session_hash)

    def revoke_session(self, session_hash):
        self.sessions.pop(session_hash, None)


def test_login_token_can_only_be_used_once():
    repository = FakeAuthRepository()
    service = AuthService(repository)

    user_id = uuid4()

    login_token = service.create_login_token(user_id)

    session_token, authenticated_user_id = (
        service.exchange_login_token(login_token)
    )

    assert authenticated_user_id == user_id
    assert service.get_authenticated_user(
        session_token
    ) == user_id

    with pytest.raises(InvalidLoginTokenError):
        service.exchange_login_token(login_token)


def test_logout_invalidates_session():
    repository = FakeAuthRepository()
    service = AuthService(repository)

    user_id = uuid4()
    login_token = service.create_login_token(user_id)

    session_token, _ = service.exchange_login_token(
        login_token
    )

    service.logout(session_token)

    assert service.get_authenticated_user(
        session_token
    ) is None
