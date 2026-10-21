
from concurrent.futures import ThreadPoolExecutor

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.task import Task, TaskSource
from app.repositories.task_repository import TaskRepository


def test_duplicate_telegram_message_creates_one_task(
    db_session,
    test_users,
):
    user, _ = test_users

    def make_task():
        return Task(
            user_id=user.id,
            title="Buy groceries",
            source=TaskSource.TELEGRAM_TEXT,
        )

    repository = TaskRepository(db_session)

    first_task, first_created = (
        repository.create_from_telegram(
            task=make_task(),
            chat_id=12345,
            message_id=100,
        )
    )

    second_task, second_created = (
        repository.create_from_telegram(
            task=make_task(),
            chat_id=12345,
            message_id=100,
        )
    )

    assert first_created is True
    assert second_created is False
    assert first_task.id == second_task.id

    count = db_session.scalar(
        select(func.count(Task.id)).where(
            Task.telegram_chat_id == 12345,
            Task.telegram_message_id == 100,
        )
    )

    assert count == 1


def test_different_messages_create_different_tasks(
    db_session,
    test_users,
):
    user, _ = test_users
    repository = TaskRepository(db_session)

    def create(message_id):
        return repository.create_from_telegram(
            task=Task(
                user_id=user.id,
                title=f"Message {message_id}",
                source=TaskSource.TELEGRAM_TEXT,
            ),
            chat_id=12345,
            message_id=message_id,
        )

    first_task, first_created = create(101)
    second_task, second_created = create(102)

    assert first_created is True
    assert second_created is True
    assert first_task.id != second_task.id


def test_concurrent_duplicate_messages_create_one_task(
    test_engine,
    db_session,
    test_users,
):
    user, _ = test_users
    user_id = user.id

    def create_task():
        # Each thread needs its own SQLAlchemy session.
        with Session(test_engine) as session:
            repository = TaskRepository(session)

            task, created = repository.create_from_telegram(
                task=Task(
                    user_id=user_id,
                    title="Concurrent message",
                    source=TaskSource.TELEGRAM_TEXT,
                ),
                chat_id=55555,
                message_id=999,
            )

            return task.id, created

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(
            executor.map(lambda _: create_task(), range(2))
        )

    task_ids = {task_id for task_id, _ in results}
    created_flags = [created for _, created in results]

    assert len(task_ids) == 1
    assert sorted(created_flags) == [False, True]

    count = db_session.scalar(
        select(func.count(Task.id)).where(
            Task.telegram_chat_id == 55555,
            Task.telegram_message_id == 999,
        )
    )

    assert count == 1
