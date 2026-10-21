
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.auth import router as auth_router
from app.api.routes.health import router as health_router
from app.api.routes.tasks import router as tasks_router
from app.core.config import get_settings
from app.api.routes.profile import router as profile_router
from app.api.routes.ws import router as ws_router

def create_app() -> FastAPI:
    settings = get_settings()

    application = FastAPI(
        title=settings.app_name,
        debug=settings.debug,
        version="0.1.0",
    )

    application.add_middleware(
        CORSMiddleware,
        allow_origins=[
            settings.frontend_url.rstrip("/")
        ],
        allow_credentials=True,
        allow_methods=[
            "GET", "POST", "PATCH", "DELETE"
        ],
        allow_headers=["Content-Type"],
    )

    application.include_router(
        health_router,
        prefix="/api/v1",
    )

    application.include_router(
        auth_router,
        prefix="/api/v1",
    )

    application.include_router(
        tasks_router,
        prefix="/api/v1",
    )

    application.include_router(
        profile_router,
        prefix="/api/v1",
    )

    application.include_router(
        ws_router,
        prefix="/api/v1",
    )
    
    return application


app = create_app()
