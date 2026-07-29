from app.evals.models import (
    EvalCase,
    ExpectedCreatedTicket,
    ExpectedTicketState,
    ExpectedToolCall,
)
from app.evals.seed import (
    OPEN_ACCOUNT_TICKET_ID,
    OPEN_BILLING_TICKET_ID,
    RESOLVED_TECHNICAL_TICKET_ID,
)
from app.tools.types import (
    ToolExecutionStatus,
    ToolFailureType,
)


CREATE_TICKET_SUBJECT = "Refund missing after cancellation"

NONEXISTENT_TICKET_ID = 999999


LIST_OPEN_TICKETS_CASE = EvalCase(
    name="list_open_tickets",
    description=(
        "The assistant should list every ticket whose status is open."
    ),
    prompts=[
        "List all open support tickets.",
    ],
    expected_tool_calls=[
        ExpectedToolCall(
            tool_name="list_tickets",
            arguments={
                "status": "open",
            },
            result_ticket_ids={
                OPEN_BILLING_TICKET_ID,
                OPEN_ACCOUNT_TICKET_ID,
            },
        )
    ],
)


GET_SPECIFIC_TICKET_CASE = EvalCase(
    name="get_specific_ticket",
    description=(
        "The assistant should retrieve the requested ticket by ID."
    ),
    prompts=[
        (
            f"Show me the complete details of ticket "
            f"{OPEN_BILLING_TICKET_ID}."
        ),
    ],
    expected_tool_calls=[
        ExpectedToolCall(
            tool_name="get_ticket",
            arguments={
                "ticket_id": OPEN_BILLING_TICKET_ID,
            },
            result_ticket_ids={
                OPEN_BILLING_TICKET_ID,
            },
        )
    ],
)


FILTER_HIGH_PRIORITY_BILLING_CASE = EvalCase(
    name="filter_high_priority_billing_tickets",
    description=(
        "The assistant should combine billing-category and "
        "high-priority filters."
    ),
    prompts=[
        "List all high-priority billing tickets.",
    ],
    expected_tool_calls=[
        ExpectedToolCall(
            tool_name="list_tickets",
            arguments={
                "category": "billing",
                "priority": "high",
            },
            result_ticket_ids={
                OPEN_BILLING_TICKET_ID,
            },
        )
    ],
)


CREATE_TICKET_CASE = EvalCase(
    name="create_ticket",
    description=(
        "The assistant should create one ticket using the supplied "
        "customer and issue details."
    ),
    prompts=[
        (
            "Create a new urgent support ticket for Neha Kapoor. "
            "Her email is neha.eval@example.com. "
            f"The subject is '{CREATE_TICKET_SUBJECT}'. "
            "The customer cancelled an order five days ago, but the "
            "refund has still not reached her bank account."
        ),
    ],
    expected_tool_calls=[
        ExpectedToolCall(
            tool_name="create_ticket",
            arguments={
                "customer_name": "Neha Kapoor",
                "customer_email": "neha.eval@example.com",
                "subject": CREATE_TICKET_SUBJECT,
                "description": (
                    "The customer cancelled an order five days ago, "
                    "but the refund has still not reached her bank "
                    "account."
                ),
                "priority": "urgent",
            },
        )
    ],
    expected_created_ticket=ExpectedCreatedTicket(
        lookup_subject=CREATE_TICKET_SUBJECT,
        fields={
            "customer_name": "Neha Kapoor",
            "customer_email": "neha.eval@example.com",
            "subject": CREATE_TICKET_SUBJECT,
            "description": (
                "The customer cancelled an order five days ago, "
                "but the refund has still not reached her bank "
                "account."
            ),
            "status": "open",
            "category": "unknown",
            "priority": "urgent",
        },
    ),
    expected_ticket_count=4,
)


UPDATE_TICKET_STATUS_CASE = EvalCase(
    name="update_ticket_status",
    description=(
        "The assistant should update the requested ticket status."
    ),
    prompts=[
        (
            f"Change ticket {OPEN_ACCOUNT_TICKET_ID} "
            "to in progress."
        ),
    ],
    expected_tool_calls=[
        ExpectedToolCall(
            tool_name="update_ticket_status",
            arguments={
                "ticket_id": OPEN_ACCOUNT_TICKET_ID,
                "status": "in_progress",
            },
            result_ticket_ids={
                OPEN_ACCOUNT_TICKET_ID,
            },
        )
    ],
    expected_ticket_states=[
        ExpectedTicketState(
            ticket_id=OPEN_ACCOUNT_TICKET_ID,
            fields={
                "status": "in_progress",
            },
        )
    ],
    expected_ticket_count=3,
)


CLASSIFY_TICKET_CASE = EvalCase(
    name="classify_ticket",
    description=(
        "The assistant should persist the requested ticket "
        "classification."
    ),
    prompts=[
        (
            f"Reclassify ticket {RESOLVED_TECHNICAL_TICKET_ID} "
            "as an account issue with urgent priority."
        ),
    ],
    expected_tool_calls=[
        ExpectedToolCall(
            tool_name="update_ticket_classification",
            arguments={
                "ticket_id": RESOLVED_TECHNICAL_TICKET_ID,
                "category": "account",
                "priority": "urgent",
            },
            result_ticket_ids={
                RESOLVED_TECHNICAL_TICKET_ID,
            },
        )
    ],
    expected_ticket_states=[
        ExpectedTicketState(
            ticket_id=RESOLVED_TECHNICAL_TICKET_ID,
            fields={
                "category": "account",
                "priority": "urgent",
                "status": "resolved",
            },
        )
    ],
    expected_ticket_count=3,
)


USE_PRIOR_CONTEXT_CASE = EvalCase(
    name="use_prior_conversation_context",
    description=(
        "The assistant should resolve 'it' using the previous "
        "conversation message."
    ),
    prompts=[
        (
            f"Show me ticket {OPEN_BILLING_TICKET_ID}."
        ),
        "Change it to resolved.",
    ],
    expected_tool_calls=[
        ExpectedToolCall(
            tool_name="get_ticket",
            arguments={
                "ticket_id": OPEN_BILLING_TICKET_ID,
            },
            result_ticket_ids={
                OPEN_BILLING_TICKET_ID,
            },
        ),
        ExpectedToolCall(
            tool_name="update_ticket_status",
            arguments={
                "ticket_id": OPEN_BILLING_TICKET_ID,
                "status": "resolved",
            },
            result_ticket_ids={
                OPEN_BILLING_TICKET_ID,
            },
        ),
    ],
    expected_ticket_states=[
        ExpectedTicketState(
            ticket_id=OPEN_BILLING_TICKET_ID,
            fields={
                "status": "resolved",
            },
        )
    ],
    expected_ticket_count=3,
)


NONEXISTENT_TICKET_CASE = EvalCase(
    name="handle_nonexistent_ticket",
    description=(
        "The assistant should handle a ticket-not-found tool result "
        "without inventing a ticket."
    ),
    prompts=[
        (
            f"Show me the complete details of ticket "
            f"{NONEXISTENT_TICKET_ID}."
        ),
    ],
    expected_tool_calls=[
        ExpectedToolCall(
            tool_name="get_ticket",
            arguments={
                "ticket_id": NONEXISTENT_TICKET_ID,
            },
            expected_status=ToolExecutionStatus.FAILED,
            expected_failure_type=ToolFailureType.NOT_FOUND,
        )
    ],
    expected_ticket_count=3,
)


REJECT_DELETION_CASE = EvalCase(
    name="reject_unsupported_deletion",
    description=(
        "The assistant should reject permanent deletion without "
        "calling a ticket mutation tool."
    ),
    prompts=[
        (
            f"Permanently delete ticket "
            f"{OPEN_BILLING_TICKET_ID}."
        ),
    ],
    expected_tool_calls=[],
    expected_ticket_states=[
        ExpectedTicketState(
            ticket_id=OPEN_BILLING_TICKET_ID,
            fields={
                "status": "open",
                "category": "billing",
                "priority": "high",
            },
        )
    ],
    expected_ticket_count=3,
)


MULTI_TOOL_WORKFLOW_CASE = EvalCase(
    name="complete_multi_tool_workflow",
    description=(
        "The assistant should inspect, update, and classify a ticket "
        "in one agent request."
    ),
    prompts=[
        (
            f"First inspect ticket {OPEN_ACCOUNT_TICKET_ID}. "
            "Then change its status to resolved and classify it as "
            "a general issue with high priority."
        ),
    ],
    expected_tool_calls=[
        ExpectedToolCall(
            tool_name="get_ticket",
            arguments={
                "ticket_id": OPEN_ACCOUNT_TICKET_ID,
            },
            result_ticket_ids={
                OPEN_ACCOUNT_TICKET_ID,
            },
        ),
        ExpectedToolCall(
            tool_name="update_ticket_status",
            arguments={
                "ticket_id": OPEN_ACCOUNT_TICKET_ID,
                "status": "resolved",
            },
            result_ticket_ids={
                OPEN_ACCOUNT_TICKET_ID,
            },
        ),
        ExpectedToolCall(
            tool_name="update_ticket_classification",
            arguments={
                "ticket_id": OPEN_ACCOUNT_TICKET_ID,
                "category": "general",
                "priority": "high",
            },
            result_ticket_ids={
                OPEN_ACCOUNT_TICKET_ID,
            },
        ),
    ],
    expected_ticket_states=[
        ExpectedTicketState(
            ticket_id=OPEN_ACCOUNT_TICKET_ID,
            fields={
                "status": "resolved",
                "category": "general",
                "priority": "high",
            },
        )
    ],
    expected_ticket_count=3,
)


EVAL_CASES = [
    LIST_OPEN_TICKETS_CASE,
    GET_SPECIFIC_TICKET_CASE,
    FILTER_HIGH_PRIORITY_BILLING_CASE,
    CREATE_TICKET_CASE,
    UPDATE_TICKET_STATUS_CASE,
    CLASSIFY_TICKET_CASE,
    USE_PRIOR_CONTEXT_CASE,
    NONEXISTENT_TICKET_CASE,
    REJECT_DELETION_CASE,
    MULTI_TOOL_WORKFLOW_CASE,
]