"""OllamaTriage - fully offline path: a ~1B model in the `ollama` Compose container.

Same interface, same prompt, same validation as LLMTriage. No key, no network,
no rate limit, and no PII leaves the machine - but slower on CPU and noticeably
worse at classification (the buy-versus-host trade-off, measured not asserted).
"""

from collections.abc import Callable
from typing import Any

import httpx
from pydantic import ValidationError

from app.providers.triage.base import MalformedTriageOutput, TriageResult
from app.providers.triage.prompt import build_messages
from app.providers.triage.retry import call_with_retry, is_retryable_status


def is_retryable_httpx_error(exc: Exception) -> bool:
    if isinstance(exc, httpx.TimeoutException | httpx.TransportError):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return is_retryable_status(exc.response.status_code)
    return False


class OllamaTriage:
    name = "llm:ollama"

    def __init__(
        self,
        base_url: str,
        model: str,
        timeout_seconds: float = 10.0,
        client: httpx.Client | None = None,
        sleep: Callable[[float], None] | None = None,
    ) -> None:
        self.model = model
        self.client = client or httpx.Client(base_url=base_url, timeout=timeout_seconds)
        self._sleep = sleep

    def _call(self, text: str, location: str) -> str:
        response = self.client.post(
            "/api/chat",
            json={
                "model": self.model,
                "messages": build_messages(text, location),
                "format": "json",
                "stream": False,
                "options": {"temperature": 0},
            },
        )
        response.raise_for_status()
        content = response.json().get("message", {}).get("content", "")
        if not content:
            raise MalformedTriageOutput("empty response from ollama")
        return str(content)

    def triage(self, text: str, location: str) -> TriageResult:
        kwargs: dict[str, Any] = {}
        if self._sleep is not None:
            kwargs["sleep"] = self._sleep
        raw = call_with_retry(
            lambda: self._call(text, location), is_retryable_httpx_error, **kwargs
        )
        try:
            return TriageResult.model_validate_json(raw)
        except ValidationError as exc:
            raise MalformedTriageOutput(f"model output failed schema validation: {exc}") from exc
