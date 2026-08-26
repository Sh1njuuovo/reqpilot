"""Provider implementations and factory."""

from __future__ import annotations

from reqpilot.config import Settings
from reqpilot.models import ProviderName
from reqpilot.providers.base import LLMProvider, ProviderError
from reqpilot.providers.llm import OpenAICompatibleProvider
from reqpilot.providers.mock import MockProvider

__all__ = ["LLMProvider", "MockProvider", "OpenAICompatibleProvider", "ProviderError", "get_provider"]


def get_provider(name: ProviderName | str, settings: Settings | None = None) -> LLMProvider:
    settings = settings or Settings.from_env()
    if name == "mock":
        return MockProvider()
    if name == "llm":
        if not settings.llm_api_key:
            raise ProviderError(
                "LLM provider selected but no API key found; set DEEPSEEK_API_KEY or OPENAI_API_KEY"
            )
        return OpenAICompatibleProvider(settings)
    raise ProviderError(f"unknown provider: {name}")
