"""Deterministic provider double for the agent loop.

The agent loop must be testable without a network call, so this double replays a
fixed script of step decisions. It records every message list it received, which
lets tests assert what the model was shown.
"""

from __future__ import annotations

from typing import Any

from reqpilot.models import AgentDecision, ToolCallRequest
from reqpilot.providers.base import ProviderError


def call(tool_name: str, **arguments: Any) -> AgentDecision:
    """One step that calls a single tool."""

    return AgentDecision(tool_calls=[ToolCallRequest(name=tool_name, arguments=arguments)])


def calls(*requests: tuple[str, dict[str, Any]], thought: str = "") -> AgentDecision:
    """One step that calls several tools at once."""

    return AgentDecision(
        thought=thought,
        tool_calls=[ToolCallRequest(name=name, arguments=args) for name, args in requests],
    )


def finish(thought: str = "") -> AgentDecision:
    """One step that claims the goal is complete."""

    return AgentDecision(thought=thought, claim_goal_complete=True)


class ScriptedAgentProvider:
    """Replays a fixed list of decisions, then either stalls or fails."""

    name = "scripted"

    def __init__(
        self,
        script: list[AgentDecision],
        *,
        on_exhausted: AgentDecision | None = None,
    ) -> None:
        self.script = list(script)
        self.on_exhausted = on_exhausted
        self.calls = 0
        self.seen_messages: list[list[dict[str, Any]]] = []
        self.seen_tools: list[list[dict[str, Any]]] = []

    def plan_step(
        self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]
    ) -> AgentDecision:
        self.seen_messages.append([dict(message) for message in messages])
        self.seen_tools.append(list(tools))
        index = self.calls
        self.calls += 1
        if index < len(self.script):
            return self.script[index]
        if self.on_exhausted is not None:
            return self.on_exhausted
        raise ProviderError("scripted provider exhausted")
