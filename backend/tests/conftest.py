import os
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker

from app.db import models  # noqa: F401
from app.db.base import Base
from app.db.session import get_db
from app.main import app


TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    (
        "postgresql+psycopg://supportpilot:supportpilot"
        "@localhost:5433/supportpilot_test"
    ),
)


# Create supportpilot_test automatically inside that same Postgres container if it does not exist yet.
def ensure_test_database_exists(database_url: str) -> None:
    """
    Create the configured test database when the local Postgres service
    is running but the test database has not been created yet.
    """
    url = make_url(database_url)
    database_name = url.database

    if database_name is None:
        return

    maintenance_url = url.set(database="postgres")
    maintenance_engine = create_engine(
        maintenance_url,
        isolation_level="AUTOCOMMIT",
        pool_pre_ping=True,
    )

    try:
        with maintenance_engine.connect() as connection:
            database_exists = connection.scalar(
                text(
                    "SELECT 1 FROM pg_database "
                    "WHERE datname = :database_name"
                ),
                {"database_name": database_name},
            )

            if database_exists is None:
                quoted_database_name = database_name.replace('"', '""')
                connection.execute(
                    text(f'CREATE DATABASE "{quoted_database_name}"')
                )
    finally:
        maintenance_engine.dispose()


ensure_test_database_exists(TEST_DATABASE_URL)

test_engine = create_engine(
    TEST_DATABASE_URL,
    pool_pre_ping=True,
)

TestingSessionLocal = sessionmaker(
    bind=test_engine,
    autoflush=False,
    autocommit=False,
)


# Pytest fixture to reset the test database before each test.
# A fixture is a function that prepares something a test needs. It runs before the test and can clean up afterward.
# The `autouse=True` parameter means this fixture will run automatically for every test without needing to be explicitly requested.
@pytest.fixture(autouse=True)
def reset_test_database(
    request: pytest.FixtureRequest,
) -> Generator[None, None, None]:
    """
    Recreate the test tables before every test.

    This gives every test a clean and predictable database.
    """
    if request.node.get_closest_marker("no_db") is not None:
        yield
        return

    Base.metadata.drop_all(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)

    yield

    Base.metadata.drop_all(bind=test_engine)


# Pytest fixture to provide a FastAPI test client that uses the test database.
@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    """
    Provide a FastAPI test client that uses the test database.
    """

    # Function to override the get_db dependency to use the test database session.
    def override_get_db() -> Generator[Session, None, None]:
        db = TestingSessionLocal()

        try:
            yield db
        finally:
            db.close()

    # Override the get_db dependency to use the test database session.
    app.dependency_overrides[get_db] = override_get_db

    # Use the TestClient to make requests to the FastAPI app.
    with TestClient(app) as test_client:
        yield test_client

    # Clear the dependency overrides after the test is done.
    app.dependency_overrides.clear()


# Pytest fixture to provide a test database session for service-layer tests.
@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    """
    Provide a direct test database session for service-layer tests.

    API tests use the client fixture and FastAPI dependency override.
    Service tests request this fixture directly.
    """
    db = TestingSessionLocal()

    try:
        yield db
    finally:
        db.close()
