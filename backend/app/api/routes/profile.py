
from fastapi import APIRouter
from pydantic import BaseModel
from uuid import UUID

from app.dependencies.auth import CurrentUserDep


router = APIRouter(prefix="/auth", tags=["Authentication"])


class CurrentUserResponse(BaseModel):
    id: UUID


@router.get("/me", response_model=CurrentUserResponse)
def get_me(current_user: CurrentUserDep):
    return CurrentUserResponse(id=current_user.id)
