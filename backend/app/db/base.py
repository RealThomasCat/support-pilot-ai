from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass

# Import models so Alembic can discover their tables.
from app.db.models.ticket import Ticket  # noqa: E402, F401