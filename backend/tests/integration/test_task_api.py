
from uuid import UUID

from app.models.task import Task, TaskSource


ORIGIN = {"Origin": "http://localhost:5173"}
def test_tasks_require_authentication(client):
    response = client.get("/api/v1/tasks")

    assert response.status_code == 401


def test_user_cannot_read_another_users_task(
    authenticated_client,
    db_session,
    test_users,
):
    _, user_b = test_users

    task = Task(
        user_id=user_b.id,
        title="Private task belonging to User B",
        source=TaskSource.WEB,
    )
    db_session.add(task)
    db_session.commit()
    db_session.refresh(task)

    response = authenticated_client.get(
        f"/api/v1/tasks/{task.id}"
    )

    # The API may use 403 or 404 depending on its
    # authorization design.
    assert response.status_code in (403, 404)


def test_user_cannot_update_another_users_task(
    authenticated_client,
    db_session,
    test_users,
):
    _, user_b = test_users

    task = Task(
        user_id=user_b.id,
        title="User B task",
        source=TaskSource.WEB,
    )
    db_session.add(task)
    db_session.commit()
    db_session.refresh(task)

    response = authenticated_client.patch(
        f"/api/v1/tasks/{task.id}",
        json={"status": "completed"},
        headers={
            "Origin": "http://localhost:5173"
        },
    )

    assert response.status_code in (403, 404)

    db_session.refresh(task)
    assert task.status.value == "pending"


def test_user_cannot_delete_another_users_task(
    authenticated_client,
    db_session,
    test_users,
):
    _, user_b = test_users

    task = Task(
        user_id=user_b.id,
        title="User B protected task",
        source=TaskSource.WEB,
    )
    db_session.add(task)
    db_session.commit()
    db_session.refresh(task)

    response = authenticated_client.delete(
        f"/api/v1/tasks/{task.id}",
        headers={
            "Origin": "http://localhost:5173"
        },
    )

    assert response.status_code in (403, 404)

    assert db_session.get(Task, task.id) is not None

def test_authenticated_user_can_create_task(
    authenticated_client,
    db_session,
    test_users,
):
    user_a, _ = test_users

    response = authenticated_client.post(
        "/api/v1/tasks",
        json={
            "title": "Write integration tests",
            "description": "Test task creation through FastAPI",
        },
        headers=ORIGIN,
    )

    assert response.status_code == 201, response.text

    data = response.json()

    assert data["title"] == "Write integration tests"
    assert data["status"] == "pending"
    assert data["source"] == "web"
    assert UUID(data["user_id"]) == user_a.id

    task = db_session.get(Task, UUID(data["id"]))
    assert task is not None
    assert task.user_id == user_a.id


def test_user_only_lists_own_tasks(
    authenticated_client,
    db_session,
    test_users,
):
    user_a, user_b = test_users

    db_session.add_all([
        Task(
            user_id=user_a.id,
            title="User A task",
            source=TaskSource.WEB,
        ),
        Task(
            user_id=user_b.id,
            title="User B private task",
            source=TaskSource.WEB,
        ),
    ])
    db_session.commit()

    response = authenticated_client.get("/api/v1/tasks")

    assert response.status_code == 200, response.text

    data = response.json()
    titles = {task["title"] for task in data}

    assert "User A task" in titles
    assert "User B private task" not in titles
    assert all(
        UUID(task["user_id"]) == user_a.id
        for task in data
    )


def test_user_can_update_own_task(
    authenticated_client,
    db_session,
    test_users,
):
    user_a, _ = test_users

    task = Task(
        user_id=user_a.id,
        title="Implement API tests",
        source=TaskSource.WEB,
    )

    db_session.add(task)
    db_session.commit()
    db_session.refresh(task)

    response = authenticated_client.patch(
        f"/api/v1/tasks/{task.id}",
        json={"status": "in_progress"},
        headers=ORIGIN,
    )

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "in_progress"

    db_session.expire_all()
    updated_task = db_session.get(Task, task.id)

    assert updated_task is not None
    assert updated_task.status.value == "in_progress"


def test_user_can_delete_own_task(
    authenticated_client,
    db_session,
    test_users,
):
    user_a, _ = test_users

    task = Task(
        user_id=user_a.id,
        title="Task to delete",
        source=TaskSource.WEB,
    )

    db_session.add(task)
    db_session.commit()
    db_session.refresh(task)
    task_id = task.id

    response = authenticated_client.delete(
        f"/api/v1/tasks/{task_id}",
        headers=ORIGIN,
    )

    assert response.status_code in (200, 204), response.text

    db_session.expire_all()
    assert db_session.get(Task, task_id) is None
