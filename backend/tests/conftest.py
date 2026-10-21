
import os

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

import app.models  # Register all SQLAlchemy models
from app.db.base import Base

from fastapi.testclient import TestClient
from app.main import app
from app.db.session import get_db

from uuid import uuid4

from app.api.routes.auth import COOKIE_NAME
from app.models.user import User
from app.repositories.auth_repository import AuthRepository
from app.services.auth_service import AuthService

from alembic import command
from alembic.config import Config
from pathlib import Path

TEST_DB_NAME = "taskbot_test"


def get_test_database_url() -> str:
    database_url = os.environ.get("TEST_DATABASE_URL")

    if not database_url:
        raise RuntimeError(
            "TEST_DATABASE_URL must be configured"
        )

    url = make_url(database_url)

    # Never run destructive test setup on development DB.
    if url.database != TEST_DB_NAME:
        raise RuntimeError(
            f"Refusing to test against {url.database!r}. "
            f"Expected {TEST_DB_NAME!r}."
        )

    if url.host not in {"localhost", "127.0.0.1"}:
        raise RuntimeError(
            "Tests must connect to local PostgreSQL"
        )

    return database_url


from pathlib import Path

from alembic import command
from alembic.config import Config


@pytest.fixture(scope="session")
def test_engine():
    database_url = get_test_database_url()

    config = Config(
        str(Path(__file__).resolve().parents[1] / "alembic.ini")
    )

    previous_url = os.environ.get(
        "ALEMBIC_TEST_DATABASE_URL"
    )

    os.environ["ALEMBIC_TEST_DATABASE_URL"] = database_url

    engine = None

    try:
        command.upgrade(config, "head")

        engine = create_engine(
            database_url,
            pool_pre_ping=True,
        )

        yield engine

    finally:
        if engine is not None:
            engine.dispose()

        if previous_url is None:
            os.environ.pop(
                "ALEMBIC_TEST_DATABASE_URL",
                None,
            )
        else:
            os.environ["ALEMBIC_TEST_DATABASE_URL"] = (
                previous_url
            )

@pytest.fixture
def db_session(test_engine):
    # Repository methods commit transactions, so we
    # explicitly clean the isolated test database.
    with test_engine.begin() as connection:
        table_names = list(Base.metadata.tables.keys())

        if table_names:
            preparer = test_engine.dialect.identifier_preparer
            names = ", ".join(
                preparer.quote(name)
                for name in table_names
            )

            connection.execute(
                text(
                    f"TRUNCATE TABLE {names} "
                    "RESTART IDENTITY CASCADE"
                )
            )

    with Session(test_engine) as session:
        yield session
        session.rollback()



@pytest.fixture
def client(db_session):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
def test_users(db_session):
    user_a = User(telegram_id=111111111)
    user_b = User(telegram_id=222222222)

    db_session.add_all([user_a, user_b])
    db_session.commit()

    db_session.refresh(user_a)
    db_session.refresh(user_b)

    return user_a, user_b


@pytest.fixture
def authenticated_client(client, db_session, test_users):
    user_a, _ = test_users

    auth_service = AuthService(
        AuthRepository(db_session)
    )

    login_token = auth_service.create_login_token(user_a.id)
    session_token, _ = auth_service.exchange_login_token(
        login_token
    )

    client.cookies.set(COOKIE_NAME, session_token)

    return client
