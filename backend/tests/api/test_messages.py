from datetime import datetime
from typing import Any

from fastapi.testclient import TestClient
from google.genai import types
from pytest import MonkeyPatch

from app.integrations.llm.gemini_provider import (
    GeminiRequestError,
    GeminiTurn,
)

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.tool_call import ToolCall
from app.db.models.ticket import (
    Ticket,
    TicketCategory,
    TicketPriority,
    TicketStatus,
)

from app.tools.types import (
    ToolExecutionStatus,
    ToolFailureType,
)


def create_conversation(
    client: TestClient,
    *,
    title: str = "Support conversation",
) -> dict[str, Any]:
    response = client.post(
        "/conversations",
        json={"title": title},
    )

    assert response.status_code == 201

    return response.json()


def final_text_turn(
    text: str,
) -> GeminiTurn:
    """
    Create a mocked Gemini turn containing final assistant text
    and no function calls.
    """
    return GeminiTurn(
        content=types.Content(
            role="model",
            parts=[
                types.Part.from_text(
                    text=text,
                )
            ],
        ),
        function_calls=[],
        text=text,
    )


def mock_gemini_response(
    monkeypatch: MonkeyPatch,
    *,
    response_text: str = "Mock assistant response.",
) -> None:
    """
    Replace the real Gemini call with a deterministic local function.

    The patch targets chat_service because that is where
    generate_model_turn is imported and called.
    """

    def fake_generate_model_turn(
        *,
        contents: list[types.Content],
    ) -> GeminiTurn:
        assert contents

        return final_text_turn(response_text)

    monkeypatch.setattr(
        "app.services.chat_service.generate_model_turn",
        fake_generate_model_turn,
    )


def function_call_turn(
    *,
    call_id: str,
    name: str,
    arguments: dict[str, Any],
) -> GeminiTurn:
    function_call = types.FunctionCall(
        id=call_id,
        name=name,
        args=arguments,
    )

    content = types.Content(
        role="model",
        parts=[
            types.Part(
                function_call=function_call,
            )
        ],
    )

    return GeminiTurn(
        content=content,
        function_calls=[function_call],
        text=None,
    )


def create_ticket(
    client: TestClient,
    *,
    customer_name: str = "Aarav Sharma",
    customer_email: str = "aarav@example.com",
    subject: str = "Duplicate payment",
    description: str = "The customer was charged twice.",
    priority: str = TicketPriority.HIGH.value,
) -> dict[str, Any]:
    """
    Create one predictable ticket through the public API.
    """
    response = client.post(
        "/tickets",
        json={
            "customer_name": customer_name,
            "customer_email": customer_email,
            "subject": subject,
            "description": description,
            "priority": priority,
        },
    )

    assert response.status_code == 201

    return response.json()


def multiple_function_calls_turn(
    calls: list[tuple[str, str, dict[str, Any]]],
) -> GeminiTurn:
    """
    Create one mocked Gemini turn containing multiple function calls.

    Each tuple contains:
        call ID, tool name, arguments
    """
    function_calls = [
        types.FunctionCall(
            id=call_id,
            name=name,
            args=arguments,
        )
        for call_id, name, arguments in calls
    ]

    return GeminiTurn(
        content=types.Content(
            role="model",
            parts=[
                types.Part(
                    function_call=function_call,
                )
                for function_call in function_calls
            ],
        ),
        function_calls=function_calls,
        text=None,
    )


def test_create_and_list_chat_messages_in_order(
    client: TestClient,
    monkeypatch: MonkeyPatch,
) -> None:
    mock_gemini_response(
        monkeypatch,
        response_text="Mock assistant response.",
    )

    conversation = create_conversation(client)
    conversation_id = conversation["id"]

    first_response = client.post(
        f"/conversations/{conversation_id}/messages",
        json={
            "content": "Find the duplicate-payment ticket.",
        },
    )
    second_response = client.post(
        f"/conversations/{conversation_id}/messages",
        json={
            "content": "Also check its priority.",
        },
    )

    assert first_response.status_code == 201
    assert second_response.status_code == 201

    first_chat = first_response.json()
    second_chat = second_response.json()

    first_user_message = first_chat["user_message"]
    first_assistant_message = first_chat["assistant_message"]

    second_user_message = second_chat["user_message"]
    second_assistant_message = second_chat["assistant_message"]

    assert first_user_message["conversation_id"] == conversation_id
    assert first_user_message["role"] == "user"
    assert first_user_message["content"] == (
        "Find the duplicate-payment ticket."
    )
    assert first_user_message["created_at"] is not None

    assert first_assistant_message["conversation_id"] == conversation_id
    assert first_assistant_message["role"] == "assistant"
    assert first_assistant_message["content"] == (
        "Mock assistant response."
    )
    assert first_assistant_message["created_at"] is not None

    assert second_user_message["conversation_id"] == conversation_id
    assert second_user_message["role"] == "user"
    assert second_user_message["content"] == (
        "Also check its priority."
    )

    assert second_assistant_message["conversation_id"] == conversation_id
    assert second_assistant_message["role"] == "assistant"
    assert second_assistant_message["content"] == (
        "Mock assistant response."
    )

    history_response = client.get(
        f"/conversations/{conversation_id}/messages",
    )

    assert history_response.status_code == 200

    history = history_response.json()

    assert len(history) == 4

    assert [message["id"] for message in history] == [
        first_user_message["id"],
        first_assistant_message["id"],
        second_user_message["id"],
        second_assistant_message["id"],
    ]

    assert [message["role"] for message in history] == [
        "user",
        "assistant",
        "user",
        "assistant",
    ]

    assert [message["content"] for message in history] == [
        "Find the duplicate-payment ticket.",
        "Mock assistant response.",
        "Also check its priority.",
        "Mock assistant response.",
    ]


def test_full_ordered_history_is_sent_to_gemini(
    client: TestClient,
    monkeypatch: MonkeyPatch,
) -> None:
    provider_calls: list[list[tuple[str, str]]] = []

    def fake_generate_model_turn(
        *,
        contents: list[types.Content],
    ) -> GeminiTurn:
        captured_contents: list[tuple[str, str]] = []

        for content in contents:
            text = ""

            for part in content.parts or []:
                if part.text is not None:
                    text += part.text

            captured_contents.append(
                (
                    content.role or "",
                    text,
                )
            )

        provider_calls.append(captured_contents)

        if len(provider_calls) == 1:
            return final_text_turn(
                "Ask for both transaction IDs."
            )

        return final_text_turn(
            "Both IDs help identify and compare the charges."
        )

    monkeypatch.setattr(
        "app.services.chat_service.generate_model_turn",
        fake_generate_model_turn,
    )

    conversation = create_conversation(client)
    conversation_id = conversation["id"]

    first_response = client.post(
        f"/conversations/{conversation_id}/messages",
        json={
            "content": "A customer says they were charged twice.",
        },
    )

    second_response = client.post(
        f"/conversations/{conversation_id}/messages",
        json={
            "content": "Why do we need both transaction IDs?",
        },
    )

    assert first_response.status_code == 201
    assert second_response.status_code == 201

    assert len(provider_calls) == 2

    assert provider_calls[0] == [
        (
            "user",
            "A customer says they were charged twice.",
        ),
    ]

    assert provider_calls[1] == [
        (
            "user",
            "A customer says they were charged twice.",
        ),
        (
            "model",
            "Ask for both transaction IDs.",
        ),
        (
            "user",
            "Why do we need both transaction IDs?",
        ),
    ]


def test_provider_failure_returns_503_and_keeps_user_message(
    client: TestClient,
    monkeypatch: MonkeyPatch,
) -> None:
    def fake_generate_model_turn(
        *,
        contents: list[types.Content],
    ) -> GeminiTurn:
        assert contents

        raise GeminiRequestError(
            "Gemini request failed.",
        )

    monkeypatch.setattr(
        "app.services.chat_service.generate_model_turn",
        fake_generate_model_turn,
    )

    conversation = create_conversation(client)
    conversation_id = conversation["id"]

    response = client.post(
        f"/conversations/{conversation_id}/messages",
        json={
            "content": "Explain this support issue.",
        },
    )

    assert response.status_code == 503
    assert response.json() == {
        "detail": "The AI provider is temporarily unavailable."
    }

    history_response = client.get(
        f"/conversations/{conversation_id}/messages",
    )

    assert history_response.status_code == 200

    history = history_response.json()

    assert len(history) == 1
    assert history[0]["conversation_id"] == conversation_id
    assert history[0]["role"] == "user"
    assert history[0]["content"] == (
        "Explain this support issue."
    )


def test_existing_conversation_without_messages_returns_empty_list(
    client: TestClient,
) -> None:
    conversation = create_conversation(client)
    conversation_id = conversation["id"]

    response = client.get(
        f"/conversations/{conversation_id}/messages",
    )

    assert response.status_code == 200
    assert response.json() == []


def test_messages_are_isolated_between_conversations(
    client: TestClient,
    monkeypatch: MonkeyPatch,
) -> None:
    mock_gemini_response(
        monkeypatch,
        response_text="Conversation-specific mock reply.",
    )

    first_conversation = create_conversation(
        client,
        title="First conversation",
    )
    second_conversation = create_conversation(
        client,
        title="Second conversation",
    )

    first_conversation_id = first_conversation["id"]
    second_conversation_id = second_conversation["id"]

    first_message_response = client.post(
        f"/conversations/{first_conversation_id}/messages",
        json={
            "content": "Message for the first conversation.",
        },
    )
    second_message_response = client.post(
        f"/conversations/{second_conversation_id}/messages",
        json={
            "content": "Message for the second conversation.",
        },
    )

    assert first_message_response.status_code == 201
    assert second_message_response.status_code == 201

    first_history_response = client.get(
        f"/conversations/{first_conversation_id}/messages",
    )
    second_history_response = client.get(
        f"/conversations/{second_conversation_id}/messages",
    )

    assert first_history_response.status_code == 200
    assert second_history_response.status_code == 200

    first_history = first_history_response.json()
    second_history = second_history_response.json()

    assert len(first_history) == 2
    assert len(second_history) == 2

    assert [message["role"] for message in first_history] == [
        "user",
        "assistant",
    ]
    assert [message["role"] for message in second_history] == [
        "user",
        "assistant",
    ]

    assert first_history[0]["content"] == (
        "Message for the first conversation."
    )
    assert first_history[1]["content"] == (
        "Conversation-specific mock reply."
    )

    assert second_history[0]["content"] == (
        "Message for the second conversation."
    )
    assert second_history[1]["content"] == (
        "Conversation-specific mock reply."
    )

    assert all(
        message["conversation_id"] == first_conversation_id
        for message in first_history
    )
    assert all(
        message["conversation_id"] == second_conversation_id
        for message in second_history
    )


def test_unknown_conversation_message_endpoints_return_404(
    client: TestClient,
    monkeypatch: MonkeyPatch,
) -> None:
    provider_was_called = False

    def fake_generate_model_turn(
        *,
        contents: list[types.Content],
    ) -> GeminiTurn:
        nonlocal provider_was_called

        provider_was_called = True

        return final_text_turn(
            "This should never be returned."
        )

    monkeypatch.setattr(
        "app.services.chat_service.generate_model_turn",
        fake_generate_model_turn,
    )

    create_response = client.post(
        "/conversations/999999/messages",
        json={"content": "This should not be stored."},
    )

    assert create_response.status_code == 404
    assert create_response.json() == {
        "detail": "Conversation not found"
    }
    assert provider_was_called is False

    history_response = client.get(
        "/conversations/999999/messages",
    )

    assert history_response.status_code == 404
    assert history_response.json() == {
        "detail": "Conversation not found"
    }


def test_invalid_message_content_returns_422(
    client: TestClient,
    monkeypatch: MonkeyPatch,
) -> None:
    provider_was_called = False

    def fake_generate_model_turn(
        *,
        contents: list[types.Content],
    ) -> GeminiTurn:
        nonlocal provider_was_called

        provider_was_called = True

        return final_text_turn(
            "This should never be returned."
        )

    monkeypatch.setattr(
        "app.services.chat_service.generate_model_turn",
        fake_generate_model_turn,
    )

    conversation = create_conversation(client)
    conversation_id = conversation["id"]

    empty_response = client.post(
        f"/conversations/{conversation_id}/messages",
        json={"content": ""},
    )

    assert empty_response.status_code == 422

    whitespace_response = client.post(
        f"/conversations/{conversation_id}/messages",
        json={"content": "     "},
    )

    assert whitespace_response.status_code == 422
    assert provider_was_called is False


def test_creating_chat_message_updates_conversation_updated_at(
    client: TestClient,
    monkeypatch: MonkeyPatch,
) -> None:
    mock_gemini_response(monkeypatch)

    conversation = create_conversation(client)
    conversation_id = conversation["id"]

    original_updated_at = datetime.fromisoformat(
        conversation["updated_at"],
    )

    message_response = client.post(
        f"/conversations/{conversation_id}/messages",
        json={"content": "Show me all open tickets."},
    )

    assert message_response.status_code == 201

    conversation_response = client.get(
        f"/conversations/{conversation_id}",
    )

    assert conversation_response.status_code == 200

    updated_conversation = conversation_response.json()
    new_updated_at = datetime.fromisoformat(
        updated_conversation["updated_at"],
    )

    assert new_updated_at > original_updated_at


def test_tool_execution_is_persisted_during_chat(
    client: TestClient,
    db_session: Session,
    monkeypatch: MonkeyPatch,
) -> None:
    provider_call_count = 0

    def fake_generate_model_turn(
        *,
        contents: list[types.Content],
    ) -> GeminiTurn:
        nonlocal provider_call_count
        provider_call_count += 1

        if provider_call_count == 1:
            return function_call_turn(
                call_id="call-1",
                name="get_ticket",
                arguments={
                    "ticket_id": 999999,
                },
            )

        return final_text_turn(
            "Ticket 999999 was not found."
        )

    monkeypatch.setattr(
        "app.services.chat_service.generate_model_turn",
        fake_generate_model_turn,
    )

    conversation = create_conversation(client)
    conversation_id = conversation["id"]

    response = client.post(
        f"/conversations/{conversation_id}/messages",
        json={
            "content": "Get ticket 999999.",
        },
    )

    assert response.status_code == 201

    response_data = response.json()
    user_message_id = response_data["user_message"]["id"]

    statement = select(ToolCall).where(
        ToolCall.conversation_id == conversation_id
    )

    tool_calls = list(
        db_session.scalars(statement).all()
    )

    assert len(tool_calls) == 1

    tool_call = tool_calls[0]

    assert tool_call.message_id == user_message_id
    assert tool_call.tool_name == "get_ticket"
    assert tool_call.requested_arguments == {
        "ticket_id": 999999,
    }
    assert tool_call.status == ToolExecutionStatus.FAILED
    assert tool_call.failure_type == ToolFailureType.NOT_FOUND
    assert tool_call.started_at is not None
    assert tool_call.completed_at is not None


def test_reply_draft_uses_ticket_context_without_updating_ticket(
    client: TestClient,
    db_session: Session,
    monkeypatch: MonkeyPatch,
) -> None:
    ticket = create_ticket(client)
    ticket_id = ticket["id"]

    provider_call_count = 0

    def fake_generate_model_turn(
        *,
        contents: list[types.Content],
    ) -> GeminiTurn:
        nonlocal provider_call_count
        provider_call_count += 1

        if provider_call_count == 1:
            return function_call_turn(
                call_id="get-ticket-for-draft",
                name="get_ticket",
                arguments={
                    "ticket_id": ticket_id,
                },
            )

        # Verify that the backend returned the tool result to Gemini.
        tool_contents = [
            content
            for content in contents
            if content.role == "tool"
        ]

        assert len(tool_contents) == 1

        tool_content = tool_contents[0]
        assert tool_content.parts

        function_response = tool_content.parts[0].function_response
        assert function_response is not None
        assert function_response.name == "get_ticket"

        response_data = function_response.response
        assert isinstance(response_data, dict)

        response_output = response_data.get("output")
        assert isinstance(response_output, dict)

        assert response_output["id"] == ticket_id
        assert response_output["subject"] == "Duplicate payment"

        return final_text_turn(
            "Suggested reply:\n\n"
            "Hi Aarav, we’re sorry about the duplicate charge. "
            "Our team is reviewing the payment and will update you "
            "as soon as possible."
        )

    monkeypatch.setattr(
        "app.services.chat_service.generate_model_turn",
        fake_generate_model_turn,
    )

    conversation = create_conversation(client)
    conversation_id = conversation["id"]

    response = client.post(
        f"/conversations/{conversation_id}/messages",
        json={
            "content": (
                f"Draft a customer reply for ticket {ticket_id}."
            ),
        },
    )

    assert response.status_code == 201

    response_data = response.json()

    assert response_data["assistant_message"]["content"].startswith(
        "Suggested reply:"
    )

    statement = (
        select(ToolCall)
        .where(
            ToolCall.conversation_id == conversation_id,
        )
    )

    tool_calls = list(
        db_session.scalars(statement).all()
    )

    assert len(tool_calls) == 1
    assert tool_calls[0].tool_name == "get_ticket"
    assert tool_calls[0].status == ToolExecutionStatus.SUCCESS

    persisted_ticket = db_session.get(
        Ticket,
        ticket_id,
    )

    assert persisted_ticket is not None
    assert persisted_ticket.status == TicketStatus.OPEN
    assert persisted_ticket.category == TicketCategory.UNKNOWN
    assert persisted_ticket.priority == TicketPriority.HIGH

    history_response = client.get(
        f"/conversations/{conversation_id}/messages",
    )

    assert history_response.status_code == 200

    history = history_response.json()

    # Only the normal user and final assistant messages are stored.
    assert len(history) == 2
    assert [message["role"] for message in history] == [
        "user",
        "assistant",
    ]


def test_chat_supports_sequential_tool_rounds(
    client: TestClient,
    db_session: Session,
    monkeypatch: MonkeyPatch,
) -> None:
    ticket = create_ticket(client)
    ticket_id = ticket["id"]

    provider_call_count = 0

    def fake_generate_model_turn(
        *,
        contents: list[types.Content],
    ) -> GeminiTurn:
        nonlocal provider_call_count
        provider_call_count += 1

        if provider_call_count == 1:
            return function_call_turn(
                call_id="search-ticket",
                name="list_tickets",
                arguments={
                    "search": "duplicate payment",
                },
            )

        if provider_call_count == 2:
            return function_call_turn(
                call_id="inspect-ticket",
                name="get_ticket",
                arguments={
                    "ticket_id": ticket_id,
                },
            )

        return final_text_turn(
            f"Ticket {ticket_id} is an open, high-priority "
            "duplicate-payment issue."
        )

    monkeypatch.setattr(
        "app.services.chat_service.generate_model_turn",
        fake_generate_model_turn,
    )

    conversation = create_conversation(client)
    conversation_id = conversation["id"]

    response = client.post(
        f"/conversations/{conversation_id}/messages",
        json={
            "content": (
                "Find the duplicate-payment ticket and summarize it."
            ),
        },
    )

    assert response.status_code == 201
    assert provider_call_count == 3

    statement = (
        select(ToolCall)
        .where(
            ToolCall.conversation_id == conversation_id,
        )
        .order_by(
            ToolCall.started_at.asc(),
            ToolCall.id.asc(),
        )
    )

    tool_calls = list(
        db_session.scalars(statement).all()
    )

    assert len(tool_calls) == 2
    assert [tool_call.tool_name for tool_call in tool_calls] == [
        "list_tickets",
        "get_ticket",
    ]

    assert all(
        tool_call.status == ToolExecutionStatus.SUCCESS
        for tool_call in tool_calls
    )


def test_follow_up_request_can_use_prior_ticket_context(
    client: TestClient,
    db_session: Session,
    monkeypatch: MonkeyPatch,
) -> None:
    ticket = create_ticket(client)
    ticket_id = ticket["id"]

    provider_call_count = 0

    def fake_generate_model_turn(
        *,
        contents: list[types.Content],
    ) -> GeminiTurn:
        nonlocal provider_call_count
        provider_call_count += 1

        if provider_call_count == 1:
            return function_call_turn(
                call_id="first-get-ticket",
                name="get_ticket",
                arguments={
                    "ticket_id": ticket_id,
                },
            )

        if provider_call_count == 2:
            return final_text_turn(
                f"Ticket {ticket_id} is currently open."
            )

        if provider_call_count == 3:
            captured_text = [
                part.text
                for content in contents
                for part in (content.parts or [])
                if part.text is not None
            ]

            assert captured_text == [
                f"Show me ticket {ticket_id}.",
                f"Ticket {ticket_id} is currently open.",
                "Mark it resolved.",
            ]

            return function_call_turn(
                call_id="follow-up-status-update",
                name="update_ticket_status",
                arguments={
                    "ticket_id": ticket_id,
                    "status": TicketStatus.RESOLVED.value,
                },
            )

        return final_text_turn(
            f"Ticket {ticket_id} has been marked resolved."
        )

    monkeypatch.setattr(
        "app.services.chat_service.generate_model_turn",
        fake_generate_model_turn,
    )

    conversation = create_conversation(client)
    conversation_id = conversation["id"]

    first_response = client.post(
        f"/conversations/{conversation_id}/messages",
        json={
            "content": f"Show me ticket {ticket_id}.",
        },
    )

    assert first_response.status_code == 201

    second_response = client.post(
        f"/conversations/{conversation_id}/messages",
        json={
            "content": "Mark it resolved.",
        },
    )

    assert second_response.status_code == 201
    assert provider_call_count == 4

    persisted_ticket = db_session.get(
        Ticket,
        ticket_id,
    )

    assert persisted_ticket is not None
    assert persisted_ticket.status == TicketStatus.RESOLVED

    statement = (
        select(ToolCall)
        .where(
            ToolCall.conversation_id == conversation_id,
        )
        .order_by(ToolCall.id.asc())
    )

    tool_calls = list(
        db_session.scalars(statement).all()
    )

    assert [tool_call.tool_name for tool_call in tool_calls] == [
        "get_ticket",
        "update_ticket_status",
    ]


def test_chat_completes_read_and_write_workflow(
    client: TestClient,
    db_session: Session,
    monkeypatch: MonkeyPatch,
) -> None:
    ticket = create_ticket(client)
    ticket_id = ticket["id"]

    provider_call_count = 0

    def fake_generate_model_turn(
        *,
        contents: list[types.Content],
    ) -> GeminiTurn:
        nonlocal provider_call_count
        provider_call_count += 1

        if provider_call_count == 1:
            return function_call_turn(
                call_id="inspect-before-update",
                name="get_ticket",
                arguments={
                    "ticket_id": ticket_id,
                },
            )

        if provider_call_count == 2:
            return function_call_turn(
                call_id="resolve-ticket",
                name="update_ticket_status",
                arguments={
                    "ticket_id": ticket_id,
                    "status": TicketStatus.RESOLVED.value,
                },
            )

        return final_text_turn(
            f"Ticket {ticket_id} was reviewed and marked resolved."
        )

    monkeypatch.setattr(
        "app.services.chat_service.generate_model_turn",
        fake_generate_model_turn,
    )

    conversation = create_conversation(client)
    conversation_id = conversation["id"]

    response = client.post(
        f"/conversations/{conversation_id}/messages",
        json={
            "content": (
                f"Review ticket {ticket_id} and mark it resolved."
            ),
        },
    )

    assert response.status_code == 201

    persisted_ticket = db_session.get(
        Ticket,
        ticket_id,
    )

    assert persisted_ticket is not None
    assert persisted_ticket.status == TicketStatus.RESOLVED

    statement = (
        select(ToolCall)
        .where(
            ToolCall.conversation_id == conversation_id,
        )
        .order_by(ToolCall.id.asc())
    )

    tool_calls = list(
        db_session.scalars(statement).all()
    )

    assert [tool_call.tool_name for tool_call in tool_calls] == [
        "get_ticket",
        "update_ticket_status",
    ]

    assert all(
        tool_call.status == ToolExecutionStatus.SUCCESS
        for tool_call in tool_calls
    )