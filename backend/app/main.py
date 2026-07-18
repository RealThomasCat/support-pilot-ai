from fastapi import FastAPI

from app.api.routes import health, tickets, conversations
from app.core.config import settings


def create_app() -> FastAPI:
    app = FastAPI(title=settings.app_name)
    app.include_router(health.router)
    app.include_router(tickets.router)
    app.include_router(conversations.router)
    return app


app = create_app()
