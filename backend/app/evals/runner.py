import sys
from collections.abc import Sequence

from sqlalchemy.orm import Session

from app.evals.cases import EVAL_CASES
from app.evals.database import (
    eval_session,
    reset_eval_database,
)
from app.evals.graders import grade_eval_case
from app.evals.models import (
    EvalCase,
    EvalObservation,
    EvalResult,
    EvalStatus,
)
from app.evals.seed import seed_eval_tickets
from app.integrations.llm.gemini_provider import GeminiProviderError
from app.services.chat_service import send_chat_message
from app.services.conversation_service import create_conversation
from app.services.tool_call_service import (
    list_tool_calls_for_conversation,
)


# Function to execute a single eval case.
def execute_eval_case(
    *,
    db: Session,
    case: EvalCase,
) -> EvalObservation:
    """
    Send every case prompt through one real conversation.

    A normal case contains one prompt. A context case contains multiple
    prompts that reuse the same persisted conversation history.
    """
    conversation = create_conversation(
        db=db,
        title=f"Eval: {case.name}",
    )

    all_tool_executions = []
    final_assistant_message = None

    for prompt in case.prompts:
        chat_result = send_chat_message(
            db=db,
            conversation=conversation,
            content=prompt,
        )

        all_tool_executions.extend(
            chat_result.tool_executions
        )

        final_assistant_message = (
            chat_result.assistant_message
        )

    if final_assistant_message is None:
        raise ValueError(
            f"Eval case '{case.name}' has no prompts."
        )

    persisted_tool_calls = (
        list_tool_calls_for_conversation(
            db=db,
            conversation_id=conversation.id,
        )
    )

    return EvalObservation(
        assistant_message=final_assistant_message,
        tool_executions=all_tool_executions,
        persisted_tool_calls=persisted_tool_calls,
    )


# Function to reset and seed DB, excecute then grade a eval case.
def run_eval_case(
    case: EvalCase,
) -> EvalResult:
    """
    Reset, seed, execute, and grade one eval case.
    """
    try:
        reset_eval_database()

        with eval_session() as db:
            seed_eval_tickets(
                db=db,
            )

            observation = execute_eval_case(
                db=db,
                case=case,
            )

            return grade_eval_case(
                db=db,
                case=case,
                observation=observation,
            )

    except GeminiProviderError as exc:
        return EvalResult(
            case_name=case.name,
            status=EvalStatus.ERROR,
            reasons=[
                f"Gemini provider error: {exc}",
            ],
        )

    except Exception as exc:
        return EvalResult(
            case_name=case.name,
            status=EvalStatus.ERROR,
            reasons=[
                f"Unexpected eval error: "
                f"{type(exc).__name__}: {exc}",
            ],
        )


# Function to run all eval cases.
def run_eval_suite(
    cases: Sequence[EvalCase],
) -> list[EvalResult]:
    return [
        run_eval_case(case)
        for case in cases
    ]


# Function to print the result of an individual eval case.
def print_result(
    result: EvalResult,
) -> None:
    print(
        f"{result.status.value.upper():5} "
        f"{result.case_name}"
    )

    for reason in result.reasons:
        print(f"      {reason}")

    if result.assistant_text:
        print(
            f"      Assistant: "
            f"{result.assistant_text}"
        )


# Function to print overall results.
def print_summary(
    results: Sequence[EvalResult],
) -> None:
    passed = sum(
        result.status == EvalStatus.PASS
        for result in results
    )

    failed = sum(
        result.status == EvalStatus.FAIL
        for result in results
    )

    errors = sum(
        result.status == EvalStatus.ERROR
        for result in results
    )

    print()

    print(
        f"Eval results: {passed} passed, "
        f"{failed} failed, {errors} errors"
    )


# Run the suit and return exit code 0 or 1.
def main() -> int:
    results = run_eval_suite(
        EVAL_CASES,
    )

    for result in results:
        print_result(result)

    print_summary(results)

    has_failure = any(
        result.status in {
            EvalStatus.FAIL,
            EvalStatus.ERROR,
        }
        for result in results
    )

    return 1 if has_failure else 0


if __name__ == "__main__":
    sys.exit(main())