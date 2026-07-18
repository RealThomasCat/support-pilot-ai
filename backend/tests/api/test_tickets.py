from fastapi.testclient import TestClient

# Helper function to create a ticket payload for testing purposes.
def ticket_payload(
    *,
    customer_name: str = "Aarav Sharma",
    customer_email: str = "aarav@example.com",
    subject: str = "Duplicate payment",
    description: str = "The same payment appears twice.",
    priority: str = "high",
) -> dict[str, str]:
    return {
        "customer_name": customer_name,
        "customer_email": customer_email,
        "subject": subject,
        "description": description,
        "priority": priority,
    }


# Pytest sees the parameter named client, finds the fixture with the same name, runs it, and passes its result into the test.
def test_create_and_get_ticket(client: TestClient) -> None:
    create_response = client.post(
        "/tickets",
        json=ticket_payload(),
    )

    assert create_response.status_code == 201

    created_ticket = create_response.json()

    assert created_ticket["id"] > 0
    assert created_ticket["customer_name"] == "Aarav Sharma"
    assert created_ticket["customer_email"] == "aarav@example.com"
    assert created_ticket["subject"] == "Duplicate payment"
    assert created_ticket["status"] == "open"
    assert created_ticket["category"] == "unknown"
    assert created_ticket["priority"] == "high"
    assert created_ticket["created_at"] is not None
    assert created_ticket["updated_at"] is not None

    ticket_id = created_ticket["id"]

    get_response = client.get(f"/tickets/{ticket_id}")

    assert get_response.status_code == 200
    assert get_response.json() == created_ticket


def test_list_and_filter_tickets(client: TestClient) -> None:
    first_response = client.post(
        "/tickets",
        json=ticket_payload(
            subject="Duplicate payment",
            priority="high",
        ),
    )
    second_response = client.post(
        "/tickets",
        json=ticket_payload(
            customer_name="Meera Singh",
            customer_email="meera@example.com",
            subject="Cannot reset password",
            description="The password reset link has expired.",
            priority="medium",
        ),
    )
    third_response = client.post(
        "/tickets",
        json=ticket_payload(
            customer_name="Kabir Verma",
            customer_email="kabir@example.com",
            subject="Unexpected subscription charge",
            description="The customer was charged after cancellation.",
            priority="urgent",
        ),
    )

    assert first_response.status_code == 201
    assert second_response.status_code == 201
    assert third_response.status_code == 201

    first_ticket_id = first_response.json()["id"]
    third_ticket_id = third_response.json()["id"]

    first_update_response = client.patch(
        f"/tickets/{first_ticket_id}",
        json={
            "category": "billing",
        },
    )
    third_update_response = client.patch(
        f"/tickets/{third_ticket_id}",
        json={
            "status": "in_progress",
            "category": "billing",
        },
    )

    assert first_update_response.status_code == 200
    assert third_update_response.status_code == 200

    list_response = client.get("/tickets")

    assert list_response.status_code == 200
    assert len(list_response.json()) == 3

    open_response = client.get(
        "/tickets",
        params={"status": "open"},
    )

    assert open_response.status_code == 200
    assert len(open_response.json()) == 2
    assert all(
        ticket["status"] == "open"
        for ticket in open_response.json()
    )

    billing_response = client.get(
        "/tickets",
        params={"category": "billing"},
    )

    assert billing_response.status_code == 200
    assert len(billing_response.json()) == 2
    assert all(
        ticket["category"] == "billing"
        for ticket in billing_response.json()
    )

    urgent_response = client.get(
        "/tickets",
        params={"priority": "urgent"},
    )

    assert urgent_response.status_code == 200
    assert len(urgent_response.json()) == 1
    assert urgent_response.json()[0]["subject"] == (
        "Unexpected subscription charge"
    )

    search_response = client.get(
        "/tickets",
        params={"search": "password"},
    )

    assert search_response.status_code == 200
    assert len(search_response.json()) == 1
    assert search_response.json()[0]["subject"] == (
        "Cannot reset password"
    )


def test_partial_update_preserves_unspecified_fields(
    client: TestClient,
) -> None:
    create_response = client.post(
        "/tickets",
        json=ticket_payload(),
    )

    assert create_response.status_code == 201

    original_ticket = create_response.json()
    ticket_id = original_ticket["id"]

    update_response = client.patch(
        f"/tickets/{ticket_id}",
        json={
            "status": "resolved",
            "category": "billing",
            "priority": "urgent",
        },
    )

    assert update_response.status_code == 200

    updated_ticket = update_response.json()

    assert updated_ticket["status"] == "resolved"
    assert updated_ticket["category"] == "billing"
    assert updated_ticket["priority"] == "urgent"

    assert updated_ticket["customer_name"] == (
        original_ticket["customer_name"]
    )
    assert updated_ticket["customer_email"] == (
        original_ticket["customer_email"]
    )
    assert updated_ticket["subject"] == original_ticket["subject"]
    assert updated_ticket["description"] == (
        original_ticket["description"]
    )


def test_get_and_update_nonexistent_ticket_return_404(
    client: TestClient,
) -> None:
    get_response = client.get("/tickets/999999")

    assert get_response.status_code == 404
    assert get_response.json() == {
        "detail": "Ticket with ID 999999 was not found."
    }

    update_response = client.patch(
        "/tickets/999999",
        json={"status": "resolved"},
    )

    assert update_response.status_code == 404
    assert update_response.json() == {
        "detail": "Ticket with ID 999999 was not found."
    }


def test_invalid_enum_values_return_422(
    client: TestClient,
) -> None:
    create_response = client.post(
        "/tickets",
        json=ticket_payload(priority="critical"),
    )

    assert create_response.status_code == 422

    invalid_filter_response = client.get(
        "/tickets",
        params={"status": "pending"},
    )

    assert invalid_filter_response.status_code == 422