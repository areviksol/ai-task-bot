
from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models.login_token import LoginToken
from app.models.user_session import UserSession


class AuthRepository:
    def __init__(self, db: Session):
        self.db = db

    def create_login_token(
        self,
        user_id: UUID,
        token_hash: str,
        expires_at: datetime,
    ) -> None:
        token = LoginToken(
            id=uuid4(),
            user_id=user_id,
            token_hash=token_hash,
            expires_at=expires_at,
        )

        try:
            self.db.add(token)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

    def redeem_login_token(
        self,
        token_hash: str,
        session_hash: str,
        session_expires_at: datetime,
    ) -> UUID | None:
        now = datetime.now(timezone.utc)

        try:
            stmt = (
                update(LoginToken)
                .where(
                    LoginToken.token_hash == token_hash,
                    LoginToken.used_at.is_(None),
                    LoginToken.expires_at > now,
                )
                .values(used_at=now)
                .returning(LoginToken.user_id)
            )

            user_id = self.db.scalar(stmt)

            if user_id is None:
                self.db.rollback()
                return None

            session = UserSession(
                id=uuid4(),
                user_id=user_id,
                session_hash=session_hash,
                expires_at=session_expires_at,
            )

            self.db.add(session)
            self.db.commit()

            return user_id

        except Exception:
            self.db.rollback()
            raise

    def get_session_user_id(
        self,
        session_hash: str,
    ) -> UUID | None:
        now = datetime.now(timezone.utc)

        stmt = select(UserSession.user_id).where(
            UserSession.session_hash == session_hash,
            UserSession.expires_at > now,
            UserSession.revoked_at.is_(None),
        )

        return self.db.scalar(stmt)

    def revoke_session(self, session_hash: str) -> None:
        stmt = (
            update(UserSession)
            .where(
                UserSession.session_hash == session_hash,
                UserSession.revoked_at.is_(None),
            )
            .values(revoked_at=datetime.now(timezone.utc))
        )

        try:
            self.db.execute(stmt)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
