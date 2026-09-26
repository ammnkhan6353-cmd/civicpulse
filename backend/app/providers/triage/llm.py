"""LLMTriage - production path: a hosted model on Groq's free tier.

Groq exposes an OpenAI-compatible API, so the official openai SDK works by
changing base_url. Engineering around the call:
  * JSON mode requested (response_format=json_object) ...
  * ... and the reply is STILL validated against TriageResult (never trusted, never eval'd)
  * hard 10 s timeout on every call, SDK-level retries disabled (we control retries)
  * one jittered retry on timeout / connection error / 429 / 5xx only - never on 400
The API key is read from the environment and never logged.
"""

from collections.abc import Callable
from typing import Any

import openai
from pydantic import ValidationError

from app.providers.triage.base import MalformedTriageOutput, TriageError, TriageResult
from app.providers.triage.prompt import build_messages
from app.providers.triage.retry import call_with_retry, is_retryable_status


def is_retryable_openai_error(exc: Exception) -> bool:
    if isinstance(exc, openai.APITimeoutError | openai.APIConnectionError):
        return True
    if isinstance(exc, openai.APIStatusError):
        return is_retryable_status(exc.status_code)
    return False


class LLMTriage:
    name = "llm:groq"

    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: str,
        timeout_seconds: float = 10.0,
        client: Any | None = None,
        sleep: Callable[[float], None] | None = None,
    ) -> None:
        self.model = model
        self.client: Any = client or openai.OpenAI(
            api_key=api_key or "missing-key",
            base_url=base_url,
            timeout=timeout_seconds,
            max_retries=0,
        )
        self._sleep = sleep

    def _call(self, text: str, location: str) -> str:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=build_messages(text, location),
            response_format={"type": "json_object"},
            temperature=0,
            max_tokens=200,
        )
        content = response.choices[0].message.content
        if not content:
            raise MalformedTriageOutput("empty response from model")
        return str(content)

    def triage(self, text: str, location: str) -> TriageResult:
        kwargs: dict[str, Any] = {}
        if self._sleep is not None:
            kwargs["sleep"] = self._sleep
        raw = call_with_retry(
            lambda: self._call(text, location), is_retryable_openai_error, **kwargs
        )
        try:
            return TriageResult.model_validate_json(raw)
        except ValidationError as exc:
            raise MalformedTriageOutput(f"model output failed schema validation: {exc}") from exc
        except ValueError as exc:  # pragma: no cover - defensive
            raise TriageError(str(exc)) from exc
