import uuid
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert

from sqlalchemy.orm import Session

from app.models.user import User


class UserRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_telegram_id(
        self,
        telegram_id: int,
    ) -> User | None:
        stmt = select(User).where(
            User.telegram_id == telegram_id
        )
        return self.db.scalar(stmt)

    def upsert_telegram_user(
        self,
        telegram_id: int,
        username: str | None,
    ) -> User:
        stmt = insert(User).values(
            id=uuid.uuid4(),
            telegram_id=telegram_id,
            username=username,
        )

        stmt = stmt.on_conflict_do_update(
            index_elements=[User.telegram_id],
            set_={
                "username": stmt.excluded.username,
                "updated_at": func.now(),
            },
        ).returning(User)

        try:
            user = self.db.scalars(
                stmt,
                execution_options={
                    "populate_existing": True
                },
            ).one()

            self.db.commit()
            return user

        except Exception:
            self.db.rollback()
            raise

