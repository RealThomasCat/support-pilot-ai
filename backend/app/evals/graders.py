# This is the comparison layer.
# It receives: Expected behaviour from cases.py + Actual behaviour captured by runner.py + Final database state.
# Then it compares them and produces: PASS or FAIL with reasons.
# Its functions mainly check four things:
#   1. Did Gemini call the expected tool?
#   2. Were the important arguments correct?
#   3. Did the tool return the expected result/status?
#   4. Did the database end in the expected state?
# It also checks that tool executions were actually persisted in tool_calls.

from enum import Enum
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.ticket import Ticket
from app.evals.models import (
    EvalCase,
    EvalObservation,
    EvalResult,
    EvalStatus,
    ExpectedCreatedTicket,
    ExpectedTicketState,
    ExpectedToolCall,
)
from app.services.tool_execution_service import ToolExecutionResult


def _normalize_value(
    value: Any,
) -> Any:
    """
    Convert enums and nested structures into comparable values.
    """
    if isinstance(value, Enum):
        return value.value

    if isinstance(value, dict):
        return {
            str(key): _normalize_value(nested_value)
            for key, nested_value in value.items()
        }

    if isinstance(value, list):
        return [
            _normalize_value(item)
            for item in value
        ]

    if isinstance(value, set):
        return {
            _normalize_value(item)
            for item in value
        }

    return value


def _arguments_match(
    *,
    expected: dict[str, Any],
    actual: dict[str, Any] | None,
) -> list[str]:
    """
    Check that every expected argument exists and has the expected value.

    Extra optional arguments are allowed here. Unnecessary tool calls are
    checked separately.
    """
    reasons: list[str] = []
    normalized_actual = _normalize_value(actual or {})

    for key, expected_value in expected.items():
        normalized_expected = _normalize_value(expected_value)
        actual_value = normalized_actual.get(key)

        if actual_value != normalized_expected:
            reasons.append(
                f"Argument '{key}' expected "
                f"{normalized_expected!r}, got {actual_value!r}."
            )

    return reasons


def _extract_ticket_ids(
    result: dict[str, Any] | list[dict[str, Any]] | None,
) -> set[int]:
    """
    Extract ticket IDs from a tool result containing either one ticket
    or a list of tickets.
    """
    if result is None:
        return set()

    if isinstance(result, dict):
        ticket_id = result.get("id")

        if isinstance(ticket_id, int):
            return {ticket_id}

        return set()

    ticket_ids: set[int] = set()

    for item in result:
        ticket_id = item.get("id")

        if isinstance(ticket_id, int):
            ticket_ids.add(ticket_id)

    return ticket_ids


def _grade_tool_call(
    *,
    index: int,
    expected: ExpectedToolCall,
    actual: ToolExecutionResult,
) -> list[str]:
    reasons: list[str] = []
    call_number = index + 1

    if actual.tool_name != expected.tool_name:
        reasons.append(
            f"Tool call {call_number}: expected "
            f"'{expected.tool_name}', got '{actual.tool_name}'."
        )

        return reasons

    if actual.status != expected.expected_status:
        reasons.append(
            f"Tool call {call_number} '{actual.tool_name}': expected "
            f"status '{expected.expected_status.value}', got "
            f"'{actual.status.value}'."
        )

    if actual.failure_type != expected.expected_failure_type:
        expected_failure = (
            expected.expected_failure_type.value
            if expected.expected_failure_type is not None
            else None
        )

        actual_failure = (
            actual.failure_type.value
            if actual.failure_type is not None
            else None
        )

        reasons.append(
            f"Tool call {call_number} '{actual.tool_name}': expected "
            f"failure type {expected_failure!r}, got "
            f"{actual_failure!r}."
        )

    argument_reasons = _arguments_match(
        expected=expected.arguments,
        actual=actual.validated_arguments,
    )

    for reason in argument_reasons:
        reasons.append(
            f"Tool call {call_number} '{actual.tool_name}': {reason}"
        )

    if expected.result_ticket_ids is not None:
        actual_ticket_ids = _extract_ticket_ids(
            actual.result,
        )

        if actual_ticket_ids != expected.result_ticket_ids:
            reasons.append(
                f"Tool call {call_number} '{actual.tool_name}': "
                f"expected result ticket IDs "
                f"{sorted(expected.result_ticket_ids)}, got "
                f"{sorted(actual_ticket_ids)}."
            )

    return reasons


def _grade_tool_calls(
    *,
    case: EvalCase,
    observation: EvalObservation,
) -> list[str]:
    reasons: list[str] = []

    expected_calls = case.expected_tool_calls
    actual_calls = observation.tool_executions

    if not case.allow_extra_tool_calls:
        if len(actual_calls) != len(expected_calls):
            reasons.append(
                f"Expected {len(expected_calls)} tool call(s), "
                f"but observed {len(actual_calls)}."
            )

    elif len(actual_calls) < len(expected_calls):
        reasons.append(
            f"Expected at least {len(expected_calls)} tool call(s), "
            f"but observed {len(actual_calls)}."
        )

    comparable_count = min(
        len(expected_calls),
        len(actual_calls),
    )

    for index in range(comparable_count):
        reasons.extend(
            _grade_tool_call(
                index=index,
                expected=expected_calls[index],
                actual=actual_calls[index],
            )
        )

    return reasons


def _grade_persisted_tool_calls(
    *,
    observation: EvalObservation,
) -> list[str]:
    """
    Ensure the in-memory executions were also persisted correctly.
    """
    reasons: list[str] = []

    executions = observation.tool_executions
    persisted_calls = observation.persisted_tool_calls

    if len(executions) != len(persisted_calls):
        return [
            "Captured "
            f"{len(executions)} execution(s), but found "
            f"{len(persisted_calls)} persisted tool-call log(s)."
        ]

    for index, (execution, persisted) in enumerate(
        zip(
            executions,
            persisted_calls,
            strict=True,
        )
    ):
        call_number = index + 1

        if persisted.tool_name != execution.tool_name:
            reasons.append(
                f"Persisted tool call {call_number}: expected name "
                f"'{execution.tool_name}', got "
                f"'{persisted.tool_name}'."
            )

        if persisted.status != execution.status:
            reasons.append(
                f"Persisted tool call {call_number} "
                f"'{execution.tool_name}': execution status and "
                "persisted status do not match."
            )

        if (
            persisted.validation_status
            != execution.validation_status
        ):
            reasons.append(
                f"Persisted tool call {call_number} "
                f"'{execution.tool_name}': validation statuses "
                "do not match."
            )

        if persisted.failure_type != execution.failure_type:
            reasons.append(
                f"Persisted tool call {call_number} "
                f"'{execution.tool_name}': failure types do not match."
            )

    return reasons


def _get_ticket_field(
    *,
    ticket: Ticket,
    field_name: str,
) -> Any:
    if not hasattr(ticket, field_name):
        raise ValueError(
            f"Unsupported ticket field in eval expectation: "
            f"{field_name}"
        )

    return _normalize_value(
        getattr(ticket, field_name)
    )


def _grade_ticket_state(
    *,
    db: Session,
    expectation: ExpectedTicketState,
) -> list[str]:
    reasons: list[str] = []

    ticket = db.get(
        Ticket,
        expectation.ticket_id,
    )

    if ticket is None:
        return [
            f"Expected ticket {expectation.ticket_id} to exist, "
            "but it was not found."
        ]

    for field_name, expected_value in expectation.fields.items():
        actual_value = _get_ticket_field(
            ticket=ticket,
            field_name=field_name,
        )

        normalized_expected = _normalize_value(
            expected_value
        )

        if actual_value != normalized_expected:
            reasons.append(
                f"Ticket {expectation.ticket_id} field "
                f"'{field_name}' expected "
                f"{normalized_expected!r}, got {actual_value!r}."
            )

    return reasons


def _grade_created_ticket(
    *,
    db: Session,
    expectation: ExpectedCreatedTicket,
) -> list[str]:
    reasons: list[str] = []

    statement = select(Ticket).where(
        Ticket.subject == expectation.lookup_subject,
    )

    tickets = list(
        db.scalars(statement).all()
    )

    if not tickets:
        return [
            "Expected a created ticket with subject "
            f"{expectation.lookup_subject!r}, but none was found."
        ]

    if len(tickets) > 1:
        reasons.append(
            "Expected exactly one created ticket with subject "
            f"{expectation.lookup_subject!r}, but found "
            f"{len(tickets)}."
        )

    ticket = tickets[0]

    for field_name, expected_value in expectation.fields.items():
        actual_value = _get_ticket_field(
            ticket=ticket,
            field_name=field_name,
        )

        normalized_expected = _normalize_value(
            expected_value
        )

        if actual_value != normalized_expected:
            reasons.append(
                f"Created ticket field '{field_name}' expected "
                f"{normalized_expected!r}, got {actual_value!r}."
            )

    return reasons


def _grade_ticket_count(
    *,
    db: Session,
    expected_count: int,
) -> list[str]:
    """
    Verify the final number of persisted tickets.
    """
    statement = select(Ticket)

    actual_count = len(
        list(
            db.scalars(statement).all()
        )
    )

    if actual_count != expected_count:
        return [
            f"Expected {expected_count} ticket(s) after the eval, "
            f"but found {actual_count}."
        ]

    return []


def grade_eval_case(
    *,
    db: Session,
    case: EvalCase,
    observation: EvalObservation,
) -> EvalResult:
    """
    Grade the structured behavior and final database state of one eval.
    """
    reasons: list[str] = []

    reasons.extend(
        _grade_tool_calls(
            case=case,
            observation=observation,
        )
    )

    reasons.extend(
        _grade_persisted_tool_calls(
            observation=observation,
        )
    )

    for expectation in case.expected_ticket_states:
        reasons.extend(
            _grade_ticket_state(
                db=db,
                expectation=expectation,
            )
        )

    if case.expected_created_ticket is not None:
        reasons.extend(
            _grade_created_ticket(
                db=db,
                expectation=case.expected_created_ticket,
            )
        )

    if case.expected_ticket_count is not None:
        reasons.extend(
            _grade_ticket_count(
                db=db,
                expected_count=case.expected_ticket_count,
            )
        )

    return EvalResult(
        case_name=case.name,
        status=(
            EvalStatus.FAIL
            if reasons
            else EvalStatus.PASS
        ),
        reasons=reasons,
        assistant_text=observation.assistant_message.content,
    )