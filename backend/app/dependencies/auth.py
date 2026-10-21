
from dataclasses import dataclass
from typing import Annotated
from uuid import UUID

from fastapi import (
    Depends,
    HTTPException,
    Request,
    status,
)

from app.api.routes.auth import (
    AuthServiceDep,
    COOKIE_NAME,
)

from app.core.config import get_settings


@dataclass(frozen=True)
class CurrentUser:
    id: UUID


def get_current_user(
    request: Request,
    service: AuthServiceDep,
) -> CurrentUser:
    session_token = request.cookies.get(COOKIE_NAME)

    if not session_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    user_id = service.get_authenticated_user(
        session_token
    )

    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired or invalid",
        )

    return CurrentUser(id=user_id)


def require_safe_origin(request: Request) -> None:
    if request.method in {
        "POST", "PUT", "PATCH", "DELETE"
    }:
        expected = get_settings().frontend_url.rstrip("/")

        if request.headers.get("origin") != expected:
            raise HTTPException(
                status_code=403,
                detail="Invalid request origin",
            )


CurrentUserDep = Annotated[
    CurrentUser,
    Depends(get_current_user),
]
