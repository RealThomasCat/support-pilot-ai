from collections.abc import Sequence
from typing import Any

from fastapi.testclient import TestClient
from google.genai import types
from pytest import MonkeyPatch

from app.integrations.llm.gemini_provider import GeminiTurn


def create_conversation(
    client: TestClient,
) -> dict[str, Any]:
    response = client.post(
        "/conversations",
        json={
            "title": "Tool-loop test conversation",
        },
    )

    assert response.status_code == 201

    return response.json()


def create_ticket(
    client: TestClient,
    *,
    customer_name: str = "Riya Sharma",
    customer_email: str = "riya@example.com",
    subject: str = "Duplicate payment",
    description: str = "The customer was charged twice.",
    priority: str = "high",
) -> dict[str, Any]:
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


def final_text_turn(
    text: str,
) -> GeminiTurn:
    """
    Create a Gemini turn containing final assistant text.
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


def function_call_turn(
    *,
    calls: list[types.FunctionCall],
) -> GeminiTurn:
    """
    Create a Gemini turn containing one or more function calls.
    """
    return GeminiTurn(
        content=types.Content(
            role="model",
            parts=[
                types.Part(
                    function_call=function_call,
                )
                for function_call in calls
            ],
        ),
        function_calls=calls,
        text=None,
    )


def test_chat_executes_tool_and_returns_final_response(
    client: TestClient,
    monkeypatch: MonkeyPatch,
) -> None:
    ticket = create_ticket(client)
    conversation = create_conversation(client)

    provider_call_count = 0

    def fake_generate_model_turn(
        *,
        contents: Sequence[types.Content],
    ) -> GeminiTurn:
        nonlocal provider_call_count

        provider_call_count += 1

        if provider_call_count == 1:
            return function_call_turn(
                calls=[
                    types.FunctionCall(
                        id="get-ticket-call-1",
                        name="get_ticket",
                        args={
                            "ticket_id": ticket["id"],
                        },
                    )
                ]
            )

        tool_content = contents[-1]

        assert tool_content.role == "user"
        assert tool_content.parts is not None
        assert len(tool_content.parts) == 1

        function_response = (
            tool_content.parts[0].function_response
        )

        assert function_response is not None
        assert function_response.id == "get-ticket-call-1"
        assert function_response.name == "get_ticket"
        assert function_response.response is not None

        output = function_response.response["output"]

        assert output["id"] == ticket["id"]
        assert output["subject"] == "Duplicate payment"

        return final_text_turn(
            "Ticket details were retrieved successfully."
        )

    monkeypatch.setattr(
        "app.services.chat_service.generate_model_turn",
        fake_generate_model_turn,
    )

    response = client.post(
        (
            f"/conversations/{conversation['id']}"
            "/messages"
        ),
        json={
            "content": (
                f"Show me ticket {ticket['id']}."
            ),
        },
    )

    assert response.status_code == 201

    response_data = response.json()

    assert response_data["assistant_message"]["content"] == (
        "Ticket details were retrieved successfully."
    )

    assert provider_call_count == 2


def test_failed_tool_result_is_returned_to_gemini(
    client: TestClient,
    monkeypatch: MonkeyPatch,
) -> None:
    conversation = create_conversation(client)

    provider_call_count = 0

    def fake_generate_model_turn(
        *,
        contents: Sequence[types.Content],
    ) -> GeminiTurn:
        nonlocal provider_call_count

        provider_call_count += 1

        if provider_call_count == 1:
            return function_call_turn(
                calls=[
                    types.FunctionCall(
                        id="missing-ticket-call",
                        name="get_ticket",
                        args={
                            "ticket_id": 999999,
                        },
                    )
                ]
            )

        tool_content = contents[-1]

        assert tool_content.parts is not None
        assert len(tool_content.parts) == 1

        function_response = (
            tool_content.parts[0].function_response
        )

        assert function_response is not None
        assert function_response.id == "missing-ticket-call"
        assert function_response.name == "get_ticket"
        assert function_response.response is not None

        error = function_response.response["error"]

        assert error["type"] == "not_found"
        assert "999999" in error["message"]

        return final_text_turn(
            "Ticket 999999 could not be found."
        )

    monkeypatch.setattr(
        "app.services.chat_service.generate_model_turn",
        fake_generate_model_turn,
    )

    response = client.post(
        (
            f"/conversations/{conversation['id']}"
            "/messages"
        ),
        json={
            "content": "Show me ticket 999999.",
        },
    )

    assert response.status_code == 201
    assert response.json()["assistant_message"]["content"] == (
        "Ticket 999999 could not be found."
    )

    assert provider_call_count == 2


def test_multiple_tool_calls_in_one_turn(
    client: TestClient,
    monkeypatch: MonkeyPatch,
) -> None:
    first_ticket = create_ticket(client)

    second_ticket = create_ticket(
        client,
        customer_name="Aman Verma",
        customer_email="aman@example.com",
        subject="Password reset failure",
        description="The reset email is not arriving.",
        priority="medium",
    )

    conversation = create_conversation(client)

    provider_call_count = 0

    def fake_generate_model_turn(
        *,
        contents: Sequence[types.Content],
    ) -> GeminiTurn:
        nonlocal provider_call_count

        provider_call_count += 1

        if provider_call_count == 1:
            return function_call_turn(
                calls=[
                    types.FunctionCall(
                        id="first-ticket-call",
                        name="get_ticket",
                        args={
                            "ticket_id": first_ticket["id"],
                        },
                    ),
                    types.FunctionCall(
                        id="second-ticket-call",
                        name="get_ticket",
                        args={
                            "ticket_id": second_ticket["id"],
                        },
                    ),
                ]
            )

        tool_content = contents[-1]

        assert tool_content.role == "user"
        assert tool_content.parts is not None
        assert len(tool_content.parts) == 2

        first_response = (
            tool_content.parts[0].function_response
        )
        second_response = (
            tool_content.parts[1].function_response
        )

        assert first_response is not None
        assert second_response is not None

        assert first_response.id == "first-ticket-call"
        assert second_response.id == "second-ticket-call"

        assert first_response.response is not None
        assert second_response.response is not None

        assert (
            first_response.response["output"]["id"]
            == first_ticket["id"]
        )
        assert (
            second_response.response["output"]["id"]
            == second_ticket["id"]
        )

        return final_text_turn(
            "Both tickets were retrieved successfully."
        )

    monkeypatch.setattr(
        "app.services.chat_service.generate_model_turn",
        fake_generate_model_turn,
    )

    response = client.post(
        (
            f"/conversations/{conversation['id']}"
            "/messages"
        ),
        json={
            "content": (
                f"Show tickets {first_ticket['id']} and "
                f"{second_ticket['id']}."
            ),
        },
    )

    assert response.status_code == 201
    assert response.json()["assistant_message"]["content"] == (
        "Both tickets were retrieved successfully."
    )

    assert provider_call_count == 2


def test_tool_round_limit_returns_503_and_keeps_user_message(
    client: TestClient,
    monkeypatch: MonkeyPatch,
) -> None:
    ticket = create_ticket(client)
    conversation = create_conversation(client)

    monkeypatch.setattr(
        "app.services.chat_service.settings."
        "gemini_max_tool_rounds",
        2,
    )

    provider_call_count = 0

    def fake_generate_model_turn(
        *,
        contents: Sequence[types.Content],
    ) -> GeminiTurn:
        nonlocal provider_call_count

        provider_call_count += 1

        return function_call_turn(
            calls=[
                types.FunctionCall(
                    id=f"repeated-call-{provider_call_count}",
                    name="get_ticket",
                    args={
                        "ticket_id": ticket["id"],
                    },
                )
            ]
        )

    monkeypatch.setattr(
        "app.services.chat_service.generate_model_turn",
        fake_generate_model_turn,
    )

    response = client.post(
        (
            f"/conversations/{conversation['id']}"
            "/messages"
        ),
        json={
            "content": "Keep inspecting this ticket.",
        },
    )

    assert response.status_code == 503
    assert response.json() == {
        "detail": "The AI provider is temporarily unavailable."
    }

    assert provider_call_count == 2

    history_response = client.get(
        (
            f"/conversations/{conversation['id']}"
            "/messages"
        ),
    )

    assert history_response.status_code == 200

    history = history_response.json()

    assert len(history) == 1
    assert history[0]["role"] == "user"
    assert history[0]["content"] == (
        "Keep inspecting this ticket."
    )
