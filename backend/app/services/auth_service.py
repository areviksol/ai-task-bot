
import hashlib
import secrets

from datetime import datetime, timedelta, timezone
from uuid import UUID

from app.repositories.auth_repository import AuthRepository


class InvalidLoginTokenError(Exception):
    pass


class AuthService:
    LOGIN_TOKEN_TTL = timedelta(minutes=5)
    SESSION_TTL = timedelta(days=7)

    def __init__(self, repository: AuthRepository):
        self.repository = repository

    @staticmethod
    def _hash_token(token: str) -> str:
        return hashlib.sha256(
            token.encode("utf-8")
        ).hexdigest()

    def create_login_token(self, user_id: UUID) -> str:
        raw_token = secrets.token_urlsafe(32)

        expires_at = (
            datetime.now(timezone.utc)
            + self.LOGIN_TOKEN_TTL
        )

        self.repository.create_login_token(
            user_id=user_id,
            token_hash=self._hash_token(raw_token),
            expires_at=expires_at,
        )

        return raw_token

    def exchange_login_token(
        self,
        raw_token: str,
    ) -> tuple[str, UUID]:
        if not raw_token:
            raise InvalidLoginTokenError(
                "Login token is required"
            )

        session_token = secrets.token_urlsafe(32)

        session_expires_at = (
            datetime.now(timezone.utc)
            + self.SESSION_TTL
        )

        user_id = self.repository.redeem_login_token(
            token_hash=self._hash_token(raw_token),
            session_hash=self._hash_token(session_token),
            session_expires_at=session_expires_at,
        )

        if user_id is None:
            raise InvalidLoginTokenError(
                "Login token is invalid or expired"
            )

        return session_token, user_id

    def get_authenticated_user(
        self,
        session_token: str,
    ) -> UUID | None:
        if not session_token:
            return None

        return self.repository.get_session_user_id(
            self._hash_token(session_token)
        )

    def logout(self, session_token: str) -> None:
        if session_token:
            self.repository.revoke_session(
                self._hash_token(session_token)
            )
