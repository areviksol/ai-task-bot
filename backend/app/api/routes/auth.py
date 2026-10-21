
from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
    Response,
    status,
)
from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.db.session import get_db
from app.repositories.auth_repository import AuthRepository
from app.services.auth_service import (
    AuthService,
    InvalidLoginTokenError,
)
from sqlalchemy.orm import Session


router = APIRouter(prefix="/auth", tags=["Authentication"])

COOKIE_NAME = "taskbot_session"


class LoginExchangeRequest(BaseModel):
    token: str = Field(min_length=20, max_length=256)


def get_auth_service(
    db: Annotated[Session, Depends(get_db)],
) -> AuthService:
    return AuthService(AuthRepository(db))


AuthServiceDep = Annotated[
    AuthService,
    Depends(get_auth_service),
]


def check_request_origin(request: Request) -> None:
    settings = get_settings()
    origin = request.headers.get("origin")

    if origin != settings.frontend_url.rstrip("/"):
        raise HTTPException(
            status_code=403,
            detail="Invalid request origin",
        )


@router.post("/exchange")
def exchange_login_token(
    data: LoginExchangeRequest,
    request: Request,
    response: Response,
    service: AuthServiceDep,
):
    check_request_origin(request)

    try:
        session_token, _ = service.exchange_login_token(
            data.token
        )
    except InvalidLoginTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired login token",
        )

    settings = get_settings()

    response.set_cookie(
        key=COOKIE_NAME,
        value=session_token,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite="lax",
        max_age=7 * 24 * 60 * 60,
        path="/",
    )

    response.headers["Cache-Control"] = "no-store"

    return {"message": "Login successful"}


@router.post("/logout")
def logout(
    request: Request,
    response: Response,
    service: AuthServiceDep,
):
    check_request_origin(request)

    token = request.cookies.get(COOKIE_NAME)

    if token:
        service.logout(token)

    response.delete_cookie(
        key=COOKIE_NAME,
        path="/",
        httponly=True,
        secure=get_settings().session_cookie_secure,
        samesite="lax",
    )

    response.headers["Cache-Control"] = "no-store"

    return {"message": "Logged out"}
