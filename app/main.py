from fastapi import FastAPI

from app.config import get_settings
from app.routes import build_router


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.service_name)
    app.include_router(build_router(settings))
    return app


app = create_app()
