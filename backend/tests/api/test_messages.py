from datetime import datetime

from fastapi.testclient import TestClient


def create_conversation(
    client: TestClient,
    *,
    title: str = "Support conversation",
) -> dict:
    response = client.post(
        "/conversations",
        json={"title": title},
    )

    assert response.status_code == 201

    return response.json()


def test_create_and_list_messages_in_order(
    client: TestClient,
) -> None:
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

    first_message = first_response.json()
    second_message = second_response.json()

    assert first_message["conversation_id"] == conversation_id
    assert first_message["role"] == "user"
    assert first_message["content"] == (
        "Find the duplicate-payment ticket."
    )
    assert first_message["created_at"] is not None

    assert second_message["conversation_id"] == conversation_id
    assert second_message["role"] == "user"
    assert second_message["content"] == (
        "Also check its priority."
    )

    history_response = client.get(
        f"/conversations/{conversation_id}/messages",
    )

    assert history_response.status_code == 200

    history = history_response.json()

    assert len(history) == 2

    assert [message["id"] for message in history] == [
        first_message["id"],
        second_message["id"],
    ]

    assert [message["content"] for message in history] == [
        "Find the duplicate-payment ticket.",
        "Also check its priority.",
    ]


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
) -> None:
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
        json={"content": "Message for the first conversation."},
    )
    second_message_response = client.post(
        f"/conversations/{second_conversation_id}/messages",
        json={"content": "Message for the second conversation."},
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

    assert len(first_history) == 1
    assert len(second_history) == 1

    assert first_history[0]["content"] == (
        "Message for the first conversation."
    )
    assert second_history[0]["content"] == (
        "Message for the second conversation."
    )

    assert first_history[0]["conversation_id"] == (
        first_conversation_id
    )
    assert second_history[0]["conversation_id"] == (
        second_conversation_id
    )


def test_unknown_conversation_message_endpoints_return_404(
    client: TestClient,
) -> None:
    create_response = client.post(
        "/conversations/999999/messages",
        json={"content": "This should not be stored."},
    )

    assert create_response.status_code == 404
    assert create_response.json() == {
        "detail": "Conversation not found"
    }

    history_response = client.get(
        "/conversations/999999/messages",
    )

    assert history_response.status_code == 404
    assert history_response.json() == {
        "detail": "Conversation not found"
    }


def test_invalid_message_content_returns_422(
    client: TestClient,
) -> None:
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


def test_creating_message_updates_conversation_updated_at(
    client: TestClient,
) -> None:
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