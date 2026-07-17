from fastapi import FastAPI

from app.api.routes import health, tickets
from app.core.config import settings


def create_app() -> FastAPI:
    app = FastAPI(title=settings.app_name)
    app.include_router(health.router)
    app.include_router(tickets.router)
    return app


app = create_app()
