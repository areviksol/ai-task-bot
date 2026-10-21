
import pytest

from app.models.user import User
from app.repositories.auth_repository import AuthRepository
from app.services.auth_service import (
    AuthService,
    InvalidLoginTokenError,
)


def test_login_token_is_single_use(db_session):
    # The test user only exists in taskbot_test.
    user = User(telegram_id=987654321)
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    service = AuthService(AuthRepository(db_session))

    login_token = service.create_login_token(user.id)

    session_token, authenticated_user_id = (
        service.exchange_login_token(login_token)
    )

    assert authenticated_user_id == user.id
    assert service.get_authenticated_user(
        session_token
    ) == user.id

    # The same token cannot be redeemed twice.
    with pytest.raises(InvalidLoginTokenError):
        service.exchange_login_token(login_token)


def test_invalid_login_token_is_rejected(db_session):
    service = AuthService(AuthRepository(db_session))

    with pytest.raises(InvalidLoginTokenError):
        service.exchange_login_token(
            "not-a-valid-login-token"
        )
