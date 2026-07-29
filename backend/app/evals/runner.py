# SupportPilot AI live eval runner.
#
# This module runs fixed eval cases through the real Gemini assistant
# workflow. Each case receives a fresh eval database with predictable
# seed data. The runner captures tool executions, grades expected
# behavior and final database state, and reports PASS, FAIL, or ERROR.
#
# Commands — run from the backend/ directory:
#
# Run all eval cases:
#   .\.venv\Scripts\python.exe -m app.evals.runner
#
# List all available eval cases:
#   .\.venv\Scripts\python.exe -m app.evals.runner --list
#
# Run one eval case:
#   .\.venv\Scripts\python.exe -m app.evals.runner --case update_ticket_status
#
# Check the exit code in PowerShell:
#   $LASTEXITCODE
#
# Exit codes:
#   0 = Every executed eval passed.
#   1 = At least one eval failed or encountered an execution error.
#   2 = Invalid command usage or invalid eval-case configuration.


import argparse
import sys
from collections.abc import Sequence
from time import perf_counter

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


EXIT_SUCCESS = 0
EXIT_EVAL_FAILURE = 1
EXIT_USAGE_ERROR = 2


# Validate eval case definitions before running the suite.
def validate_eval_cases(
    cases: Sequence[EvalCase],
) -> None:
    """
    Validate the static eval-case collection before execution.

    Duplicate names would make selecting one case ambiguous.
    Cases without prompts cannot execute a chat workflow.
    """
    seen_names: set[str] = set()

    for case in cases:
        if case.name in seen_names:
            raise ValueError(
                f"Duplicate eval case name: {case.name}"
            )

        seen_names.add(case.name)

        if not case.prompts:
            raise ValueError(
                f"Eval case '{case.name}' has no prompts."
            )


# Find an eval case by its unique name.
def find_eval_case(
    *,
    cases: Sequence[EvalCase],
    case_name: str,
) -> EvalCase | None:
    """
    Find one eval case by its unique name.
    """
    for case in cases:
        if case.name == case_name:
            return case

    return None


# Execute all prompts belonging to one eval case in one conversation.
def execute_eval_case(
    *,
    db: Session,
    case: EvalCase,
) -> EvalObservation:
    """
    Send every prompt through one real Gemini conversation.

    Multi-turn cases reuse the same conversation so previous messages
    remain available to the assistant.
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
            f"Eval case '{case.name}' produced no assistant message."
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


# Reset and seed the eval database, then execute and grade one case.
def run_eval_case(
    case: EvalCase,
) -> EvalResult:
    """
    Reset, seed, execute, and grade one isolated eval case.
    """
    started_at = perf_counter()

    try:
        # Every case receives a completely fresh database.
        reset_eval_database()

        with eval_session() as db:
            seed_eval_tickets(
                db=db,
            )

            observation = execute_eval_case(
                db=db,
                case=case,
            )

            result = grade_eval_case(
                db=db,
                case=case,
                observation=observation,
            )

    except GeminiProviderError as exc:
        result = EvalResult(
            case_name=case.name,
            status=EvalStatus.ERROR,
            reasons=[
                f"Gemini provider error: {exc}",
            ],
        )

    except Exception as exc:
        result = EvalResult(
            case_name=case.name,
            status=EvalStatus.ERROR,
            reasons=[
                f"Unexpected eval error: "
                f"{type(exc).__name__}: {exc}",
            ],
        )

    result.duration_seconds = (
        perf_counter() - started_at
    )

    return result


# Run the supplied eval cases sequentially and collect their results.
def run_eval_suite(
    cases: Sequence[EvalCase],
) -> list[EvalResult]:
    """
    Run eval cases sequentially.

    Each case resets and reseeds the eval database independently.
    """
    results: list[EvalResult] = []

    for index, case in enumerate(
        cases,
        start=1,
    ):
        print(
            f"Running {index}/{len(cases)}: "
            f"{case.name}"
        )

        result = run_eval_case(
            case,
        )

        results.append(
            result
        )

        print_result(
            result,
        )

    return results


# Print the result and failure details for one eval case.
def print_result(
    result: EvalResult,
) -> None:
    duration_text = ""

    if result.duration_seconds is not None:
        duration_text = (
            f" ({result.duration_seconds:.2f}s)"
        )

    print(
        f"{result.status.value.upper():5} "
        f"{result.case_name}"
        f"{duration_text}"
    )

    for reason in result.reasons:
        print(
            f"      {reason}"
        )

    if result.assistant_text:
        print(
            f"      Assistant: "
            f"{result.assistant_text}"
        )

    print()


# Print the overall pass, fail, error, and duration summary.
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

    total_duration = sum(
        result.duration_seconds or 0
        for result in results
    )

    print("=" * 60)

    print(
        f"Eval results: {passed} passed, "
        f"{failed} failed, "
        f"{errors} errors"
    )

    print(
        f"Cases run: {len(results)}"
    )

    print(
        f"Total duration: {total_duration:.2f}s"
    )

    print("=" * 60)


# Print the names and descriptions of all available eval cases.
def list_eval_cases(
    cases: Sequence[EvalCase],
) -> None:
    """
    Print available case names and descriptions.
    """
    print("Available eval cases:")

    for case in cases:
        print(
            f"  {case.name}"
        )

        print(
            f"    {case.description}"
        )


# Parse command-line options such as --list and --case.
def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run SupportPilot AI live Gemini eval cases."
        )
    )

    parser.add_argument(
        "--case",
        dest="case_name",
        help=(
            "Run one eval case by name. "
            "Without this option, all cases run."
        ),
    )

    parser.add_argument(
        "--list",
        action="store_true",
        help="List available eval cases and exit.",
    )

    return parser.parse_args()


# Determine the process exit code from the completed eval results.
def determine_exit_code(
    results: Sequence[EvalResult],
) -> int:
    """
    Return success only when every executed case passed.
    """
    if all(
        result.status == EvalStatus.PASS
        for result in results
    ):
        return EXIT_SUCCESS

    return EXIT_EVAL_FAILURE


# Validate configuration, process arguments, run the suite, and return an exit code.
def main() -> int:
    try:
        validate_eval_cases(
            EVAL_CASES,
        )
    except ValueError as exc:
        print(
            f"Eval configuration error: {exc}",
            file=sys.stderr,
        )

        return EXIT_USAGE_ERROR

    arguments = parse_arguments()

    if arguments.list:
        list_eval_cases(
            EVAL_CASES,
        )

        return EXIT_SUCCESS

    cases_to_run: Sequence[EvalCase]

    if arguments.case_name:
        selected_case = find_eval_case(
            cases=EVAL_CASES,
            case_name=arguments.case_name,
        )

        if selected_case is None:
            print(
                f"Unknown eval case: "
                f"{arguments.case_name}",
                file=sys.stderr,
            )

            print(
                "Use --list to view available cases.",
                file=sys.stderr,
            )

            return EXIT_USAGE_ERROR

        cases_to_run = [
            selected_case,
        ]

    else:
        cases_to_run = EVAL_CASES

    results = run_eval_suite(
        cases_to_run,
    )

    print_summary(
        results,
    )

    return determine_exit_code(
        results,
    )


if __name__ == "__main__":
    sys.exit(main())