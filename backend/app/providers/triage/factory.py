"""Select the TriageProvider from the TRIAGE_PROVIDER environment variable."""

from app.config import Settings
from app.providers.triage.base import TriageProvider
from app.providers.triage.llm import LLMTriage
from app.providers.triage.ollama import OllamaTriage
from app.providers.triage.rules import RuleBasedTriage
from app.providers.triage.simulated import SimulatedTriage

AVAILABLE_PROVIDERS = ("llm", "ollama", "rules", "simulated")


def build_triage_provider(settings: Settings) -> TriageProvider:
    choice = settings.triage_provider.strip().lower()
    if choice == "llm":
        return LLMTriage(
            api_key=settings.groq_api_key.get_secret_value(),
            model=settings.groq_model,
            base_url=settings.groq_base_url,
            timeout_seconds=settings.triage_timeout_seconds,
        )
    if choice == "ollama":
        return OllamaTriage(
            base_url=settings.ollama_url,
            model=settings.ollama_model,
            timeout_seconds=settings.triage_timeout_seconds,
        )
    if choice == "rules":
        return RuleBasedTriage()
    if choice == "simulated":
        return SimulatedTriage(failure_mode=settings.simulated_failure_mode)
    raise ValueError(
        f"Unknown TRIAGE_PROVIDER={settings.triage_provider!r}; "
        f"expected one of {', '.join(AVAILABLE_PROVIDERS)}"
    )
