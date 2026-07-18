from fastapi.testclient import TestClient


def test_create_and_get_conversation(
    client: TestClient,
) -> None:
    create_response = client.post(
        "/conversations",
        json={"title": "Billing investigation"},
    )

    assert create_response.status_code == 201

    created_conversation = create_response.json()

    assert created_conversation["id"] > 0
    assert created_conversation["title"] == "Billing investigation"
    assert created_conversation["created_at"] is not None
    assert created_conversation["updated_at"] is not None

    conversation_id = created_conversation["id"]

    get_response = client.get(
        f"/conversations/{conversation_id}",
    )

    assert get_response.status_code == 200
    assert get_response.json() == created_conversation


def test_create_conversation_uses_default_title(
    client: TestClient,
) -> None:
    response = client.post(
        "/conversations",
        json={},
    )

    assert response.status_code == 201
    assert response.json()["title"] == "New conversation"


def test_list_conversations_returns_newest_first(
    client: TestClient,
) -> None:
    first_response = client.post(
        "/conversations",
        json={"title": "First conversation"},
    )
    second_response = client.post(
        "/conversations",
        json={"title": "Second conversation"},
    )

    assert first_response.status_code == 201
    assert second_response.status_code == 201

    list_response = client.get("/conversations")

    assert list_response.status_code == 200

    conversations = list_response.json()

    assert len(conversations) == 2
    assert conversations[0]["title"] == "Second conversation"
    assert conversations[1]["title"] == "First conversation"


def test_get_nonexistent_conversation_returns_404(
    client: TestClient,
) -> None:
    response = client.get("/conversations/999999")

    assert response.status_code == 404
    assert response.json() == {
        "detail": "Conversation not found"
    }


def test_invalid_conversation_titles_return_422(
    client: TestClient,
) -> None:
    empty_response = client.post(
        "/conversations",
        json={"title": ""},
    )

    assert empty_response.status_code == 422

    whitespace_response = client.post(
        "/conversations",
        json={"title": "     "},
    )

    assert whitespace_response.status_code == 422

    too_long_response = client.post(
        "/conversations",
        json={"title": "a" * 201},
    )

    assert too_long_response.status_code == 422