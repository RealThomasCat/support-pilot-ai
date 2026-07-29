from typing import Any

import pytest
from google.genai import types
from pytest import MonkeyPatch

from app.integrations.llm import gemini_provider


pytestmark = pytest.mark.no_db


def test_generate_model_turn_passes_configured_timeout_to_client(
    monkeypatch: MonkeyPatch,
) -> None:
    captured_http_options: list[types.HttpOptions | None] = []

    class FakeCandidate:
        content = types.Content(
            role="model",
            parts=[
                types.Part.from_text(
                    text="Done.",
                )
            ],
        )

    class FakeResponse:
        candidates = [FakeCandidate()]
        function_calls: list[types.FunctionCall] = []
        text = "Done."

    class FakeClient:
        def __init__(
            self,
            *,
            api_key: str,
            http_options: types.HttpOptions | None = None,
            **_kwargs: Any,
        ) -> None:
            assert api_key == "test-api-key"
            captured_http_options.append(http_options)
            self.models = self

        def __enter__(self) -> "FakeClient":
            return self

        def __exit__(self, *_args: Any) -> None:
            return None

        def generate_content(self, **_kwargs: Any) -> FakeResponse:
            return FakeResponse()

    monkeypatch.setattr(
        gemini_provider,
        "_get_api_key",
        lambda: "test-api-key",
    )
    monkeypatch.setattr(
        gemini_provider.settings,
        "gemini_request_timeout_ms",
        12_000,
    )
    monkeypatch.setattr(
        gemini_provider.genai,
        "Client",
        FakeClient,
    )

    turn = gemini_provider.generate_model_turn(
        contents=[
            types.Content(
                role="user",
                parts=[
                    types.Part.from_text(
                        text="Hello.",
                    )
                ],
            )
        ],
    )

    assert turn.text == "Done."
    assert captured_http_options
    assert captured_http_options[0] is not None
    assert captured_http_options[0].timeout == 12_000
