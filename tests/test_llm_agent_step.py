import httpx
import pytest

from reqpilot.config import Settings
from reqpilot.providers.base import ProviderError
from reqpilot.providers.llm import OpenAICompatibleProvider, _sanitize_messages


class FakeResponse:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload
        self.request = httpx.Request("POST", "https://example.invalid/chat/completions")

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(
                f"status {self.status_code}", request=self.request, response=self
            )


def _assistant_message(tool_calls=None, content=None):
    message = {"role": "assistant", "content": content}
    if tool_calls is not None:
        message["tool_calls"] = tool_calls
    return {"choices": [{"message": message}]}


def _tool_call(name, arguments):
    return {"id": "call_1", "type": "function", "function": {"name": name, "arguments": arguments}}


@pytest.fixture()
def provider():
    return OpenAICompatibleProvider(Settings(llm_api_key="sk-test"))


def _patch_post(monkeypatch, responses):
    calls = {"count": 0}

    def fake_post(url, headers=None, json=None, timeout=None):
        index = min(calls["count"], len(responses) - 1)
        calls["count"] += 1
        return responses[index]

    monkeypatch.setattr("reqpilot.providers.llm.httpx.post", fake_post)
    monkeypatch.setattr("reqpilot.providers.llm.time.sleep", lambda _seconds: None)
    return calls


def test_plan_step_parses_tool_calls(provider, monkeypatch):
    _patch_post(
        monkeypatch,
        [FakeResponse(200, _assistant_message([_tool_call("read", '{"path": "prd.md"}')], "先看看 PRD"))],
    )
    decision = provider.plan_step([{"role": "user", "content": "go"}], [{"type": "function"}])

    assert decision.thought == "先看看 PRD"
    assert decision.claim_goal_complete is False
    assert decision.tool_calls[0].name == "read"
    assert decision.tool_calls[0].arguments == {"path": "prd.md"}


def test_goal_complete_tool_call_sets_claim(provider, monkeypatch):
    _patch_post(monkeypatch, [FakeResponse(200, _assistant_message([_tool_call("goal_complete", "{}")]))])
    decision = provider.plan_step([{"role": "user", "content": "go"}], [])

    assert decision.claim_goal_complete is True


def test_malformed_arguments_are_kept_for_the_trace(provider, monkeypatch):
    _patch_post(
        monkeypatch,
        [FakeResponse(200, _assistant_message([_tool_call("read", "{path: prd.md")]))],
    )
    decision = provider.plan_step([{"role": "user", "content": "go"}], [])

    assert decision.tool_calls[0].arguments == {"_raw_arguments": "{path: prd.md"}


def test_truncated_finish_reason_is_flagged(provider, monkeypatch):
    payload = _assistant_message([_tool_call("write", '{"path": "a.md", "content": "半')])
    payload["choices"][0]["finish_reason"] = "length"
    _patch_post(monkeypatch, [FakeResponse(200, payload)])

    decision = provider.plan_step([{"role": "user", "content": "go"}], [])

    assert decision.truncated is True


def test_normal_finish_reason_is_not_flagged(provider, monkeypatch):
    payload = _assistant_message([_tool_call("ls", "{}")])
    payload["choices"][0]["finish_reason"] = "tool_calls"
    _patch_post(monkeypatch, [FakeResponse(200, payload)])

    decision = provider.plan_step([{"role": "user", "content": "go"}], [])

    assert decision.truncated is False


def test_agent_max_tokens_is_configurable(provider, monkeypatch):
    captured = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        captured["payload"] = json
        return FakeResponse(200, _assistant_message([_tool_call("ls", "{}")]))

    monkeypatch.setattr("reqpilot.providers.llm.httpx.post", fake_post)
    OpenAICompatibleProvider(
        Settings(llm_api_key="sk-test", agent_max_tokens=1234)
    ).plan_step([{"role": "user", "content": "go"}], [])

    assert captured["payload"]["max_tokens"] == 1234


def test_summarize_uses_the_model(provider, monkeypatch):
    captured = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        captured["payload"] = json
        return FakeResponse(200, {"choices": [{"message": {"content": " 要点一到三点 "}}]})

    monkeypatch.setattr("reqpilot.providers.llm.httpx.post", fake_post)
    summary = provider.summarize([{"role": "user", "content": "长记录"}])

    assert summary == "要点一到三点"
    assert "压缩成要点" in captured["payload"]["messages"][0]["content"]


def test_transient_failure_is_retried(provider, monkeypatch):
    calls = _patch_post(
        monkeypatch,
        [
            FakeResponse(503, {}),
            FakeResponse(200, _assistant_message([_tool_call("ls", "{}")])),
        ],
    )
    decision = provider.plan_step([{"role": "user", "content": "go"}], [])

    assert decision.tool_calls[0].name == "ls"
    assert calls["count"] == 2


def test_persistent_failure_raises_provider_error(provider, monkeypatch):
    _patch_post(monkeypatch, [FakeResponse(503, {})])
    with pytest.raises(ProviderError):
        provider.plan_step([{"role": "user", "content": "go"}], [])


def test_missing_api_key_raises():
    provider = OpenAICompatibleProvider(Settings(llm_api_key=None))
    with pytest.raises(ProviderError, match="no LLM API key"):
        provider.plan_step([{"role": "user", "content": "go"}], [])


def test_sanitize_messages_drops_internal_fields():
    cleaned = _sanitize_messages(
        [
            {"role": "assistant", "content": "hi", "planned_tools": ["ls"]},
            {"role": "user", "content": "go", "name": "read"},
            {"content": "没有角色"},
        ]
    )
    assert cleaned == [
        {"role": "assistant", "content": "hi"},
        {"role": "user", "content": "go", "name": "read"},
    ]
