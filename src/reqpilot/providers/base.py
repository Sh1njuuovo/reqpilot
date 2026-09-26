"""Provider protocol shared by mock and LLM implementations."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from reqpilot.models import AgentDecision, ParsedRequirement, PRDDocument, ReviewIssue


class ProviderError(RuntimeError):
    """Raised when a provider cannot produce a valid result or is unavailable."""


@runtime_checkable
class LLMProvider(Protocol):
    name: str

    def plan_step(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> AgentDecision:
        """Decide the next agent step: which tools to call, or claim completion."""

    def summarize(self, messages: list[dict[str, Any]]) -> str:
        """Compress older transcript messages; used when the context budget is hit."""

    def parse(self, text: str, domain: str) -> ParsedRequirement:
        """Extract a schema-validated ParsedRequirement from raw text."""

    def review(self, role: str, parsed: ParsedRequirement, context: str) -> list[ReviewIssue]:
        """Run one review role over the parsed requirement and return issues."""

    def generate_prd(self, parsed: ParsedRequirement, domain: str, context: str) -> PRDDocument:
        """Generate the structured PRD document."""
