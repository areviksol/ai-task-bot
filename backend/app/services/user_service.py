
from app.models.user import User
from app.repositories.user_repository import UserRepository


class UserService:
    def __init__(
        self,
        repository: UserRepository,
    ):
        self.repository = repository

    def register_telegram_user(
        self,
        telegram_id: int,
        username: str | None,
    ) -> User:
        if telegram_id <= 0:
            raise ValueError("Invalid Telegram user ID")

        return self.repository.upsert_telegram_user(
            telegram_id=telegram_id,
            username=username,
        )
