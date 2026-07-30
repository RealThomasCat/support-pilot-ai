from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from app.api.routes import health, tickets, conversations, messages, tool_calls
from app.core.config import settings
from app.core.logging_config import configure_logging
from app.services.errors import DatabaseWriteError


async def database_write_error_handler(
    _request: Request,
    _exc: DatabaseWriteError,
) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={
            "detail": "The database is temporarily unavailable.",
        },
    )


def create_app() -> FastAPI:
    configure_logging()

    app = FastAPI(title=settings.app_name)
    app.add_exception_handler(
        DatabaseWriteError,
        database_write_error_handler,
    )
    app.include_router(health.router)
    app.include_router(tickets.router)
    app.include_router(conversations.router)
    app.include_router(messages.router)
    app.include_router(tool_calls.router)
    return app


app = create_app()
