
import os

from alembic import context
from sqlalchemy import create_engine, pool
from sqlalchemy.engine import make_url

from app.core.config import get_settings
from app.db.base import Base

# Register all SQLAlchemy models.
import app.models  # noqa: F401


config = context.config
target_metadata = Base.metadata


def resolve_database_url() -> str:
    test_url = os.environ.get("ALEMBIC_TEST_DATABASE_URL")

    if test_url:
        parsed = make_url(test_url)

        if (
            parsed.database != "taskbot_test"
            or parsed.host not in {"localhost", "127.0.0.1"}
            or parsed.port != 5433
        ):
            raise RuntimeError(
                "Refusing unsafe Alembic test database URL"
            )

        return test_url

    return get_settings().database_url.render_as_string(
        hide_password=False
    )


def run_migrations_offline() -> None:
    database_url = resolve_database_url()

    context.configure(
        url=database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    database_url = resolve_database_url()

    engine = create_engine(
        database_url,
        poolclass=pool.NullPool,
    )

    try:
        with engine.connect() as connection:
            context.configure(
                connection=connection,
                target_metadata=target_metadata,
                compare_type=True,
            )

            with context.begin_transaction():
                context.run_migrations()
    finally:
        engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
