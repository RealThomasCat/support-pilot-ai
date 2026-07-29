from collections.abc import Generator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings
from app.db import models  # noqa: F401
from app.db.base import Base


eval_engine = create_engine(
    settings.eval_database_url,
    pool_pre_ping=True,
)

# Isolated eval database session.
EvalSessionLocal = sessionmaker(
    bind=eval_engine,
    autoflush=False,
    autocommit=False,
)


def reset_eval_database() -> None:
    """
    Recreate all application tables in the isolated eval database.

    Every eval case starts from a predictable state and does not depend
    on previous eval runs.
    """
    Base.metadata.drop_all(bind=eval_engine)
    Base.metadata.create_all(bind=eval_engine)


@contextmanager
def eval_session() -> Generator[Session, None, None]:
    """
    Provide one SQLAlchemy session for an eval case.
    """
    db = EvalSessionLocal()

    try:
        yield db
    finally:
        db.close()