from typing import Any

import pytest
from sqlalchemy.exc import SQLAlchemyError

from app.db.models.conversation import Conversation
from app.db.models.message import MessageRole
from app.schemas.ticket import TicketCreate, TicketUpdate
from app.services.conversation_service import create_conversation
from app.services.errors import DatabaseWriteError
from app.services.message_service import create_message
from app.services.ticket_service import create_ticket, update_ticket


pytestmark = pytest.mark.no_db


class CommitFailureSession:
    def __init__(
        self,
        existing_object: Any | None = None,
    ) -> None:
        self.existing_object = existing_object
        self.rollback_called = False

    def add(self, _obj: Any) -> None:
        return None

    def commit(self) -> None:
        raise SQLAlchemyError("commit failed")

    def refresh(self, _obj: Any) -> None:
        return None

    def rollback(self) -> None:
        self.rollback_called = True

    def get(self, _model: type[Any], _id: int) -> Any | None:
        return self.existing_object


def test_create_ticket_rolls_back_database_write_failure() -> None:
    db = CommitFailureSession()

    with pytest.raises(DatabaseWriteError):
        create_ticket(
            ticket_data=TicketCreate(
                customer_name="Aarav Sharma",
                customer_email="aarav@example.com",
                subject="Duplicate payment",
                description="The same payment appears twice.",
                priority="high",
            ),
            db=db,  # type: ignore[arg-type]
        )

    assert db.rollback_called


def test_update_ticket_rolls_back_database_write_failure() -> None:
    db = CommitFailureSession(
        existing_object=create_ticket_model_stub(),
    )

    with pytest.raises(DatabaseWriteError):
        update_ticket(
            ticket_id=1,
            ticket_data=TicketUpdate(status="resolved"),
            db=db,  # type: ignore[arg-type]
        )

    assert db.rollback_called


def test_create_conversation_rolls_back_database_write_failure() -> None:
    db = CommitFailureSession()

    with pytest.raises(DatabaseWriteError):
        create_conversation(
            db=db,  # type: ignore[arg-type]
            title="Billing investigation",
        )

    assert db.rollback_called


def test_create_message_rolls_back_database_write_failure() -> None:
    db = CommitFailureSession()
    conversation = Conversation(
        id=1,
        title="Billing investigation",
    )

    with pytest.raises(DatabaseWriteError):
        create_message(
            db=db,  # type: ignore[arg-type]
            conversation=conversation,
            role=MessageRole.USER,
            content="Check this ticket.",
        )

    assert db.rollback_called


def create_ticket_model_stub() -> Any:
    class TicketStub:
        status = "open"

    return TicketStub()
