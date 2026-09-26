"""OpenAI-compatible LLM provider (DeepSeek and friends)."""

from __future__ import annotations

import json
import re
import time
from typing import Any

import httpx
from pydantic import ValidationError

from reqpilot.agent.loop import GOAL_COMPLETE_TOOL
from reqpilot.config import Settings
from reqpilot.models import (
    AgentDecision,
    ParsedRequirement,
    PRDDocument,
    ReviewIssue,
    ToolCallRequest,
)
from reqpilot.prompt_variants import variant_prompt
from reqpilot.providers.base import ProviderError

SYSTEM_PARSE = """你是需求分析 Agent。把用户输入的自然语言需求抽取为结构化 JSON，必须只输出 JSON 对象，不要输出解释。
JSON 字段：
{
  "background": "需求背景，没有则为 null",
  "target_users": ["目标用户"],
  "user_stories": ["作为X，我想要Y"],
  "functional_requirements": ["功能需求句子"],
  "constraints": ["规则约束"],
  "permissions": ["权限/角色描述"],
  "data_fields": [{"name": "字段名", "type": "string|number|date|enum", "required": true}],
  "exception_flows": ["异常路径"],
  "acceptance_criteria": ["验收标准"]
}
"""

ROLE_SYSTEM: dict[str, str] = {
    "product": "你是产品经理审查 Agent。检查需求的目标用户、业务目标、流程完整性与验收标准，输出问题列表。",
    "frontend": "你是前端审查 Agent。检查页面信息架构、交互、状态（空/加载/错误）、表单校验与角色差异展示，输出问题列表。",
    "backend": "你是后端审查 Agent。检查接口、数据模型、权限模型、幂等性与分页等设计，输出问题列表。",
    "test": "你是测试审查 Agent。检查边界条件、异常路径、可测试性与字段级校验用例，输出问题列表。",
}

def _strip_fences(content: str) -> str:
    content = content.strip()
    content = re.sub(r"^```(?:json)?\s*", "", content)
    content = re.sub(r"\s*```$", "", content)
    return content.strip()


def _sanitize_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Keep only the message fields the chat-completions API accepts."""

    allowed = {"role", "content", "name"}
    return [
        {key: value for key, value in message.items() if key in allowed}
        for message in messages
        if message.get("role")
    ]


def _parse_decision(message: dict[str, Any], truncated: bool = False) -> AgentDecision:
    """Turn one assistant message into a validated step decision."""

    decision = AgentDecision(
        thought=str(message.get("content") or "").strip(), truncated=truncated
    )
    for call in message.get("tool_calls") or []:
        function = call.get("function") or {}
        name = str(function.get("name") or "").strip()
        if not name:
            continue
        raw = function.get("arguments")
        if isinstance(raw, dict):
            arguments: dict[str, Any] = dict(raw)
        else:
            try:
                parsed = json.loads(raw or "{}")
            except (json.JSONDecodeError, TypeError):
                parsed = None
            arguments = parsed if isinstance(parsed, dict) else {"_raw_arguments": raw}
        if name == GOAL_COMPLETE_TOOL:
            decision.claim_goal_complete = True
        decision.tool_calls.append(ToolCallRequest(name=name, arguments=arguments))
    return decision


class OpenAICompatibleProvider:
    """Calls an OpenAI-compatible chat-completions endpoint with JSON output."""

    name = "llm"

    def __init__(self, settings: Settings):
        self.settings = settings

    def _post(self, payload: dict[str, Any]) -> dict:
        """POST one chat-completions payload; transient errors surface as exceptions."""

        if not self.settings.llm_api_key:
            raise ProviderError("no LLM API key configured")
        resp = httpx.post(
            f"{self.settings.llm_base_url.rstrip('/')}/chat/completions",
            headers={"Authorization": f"Bearer {self.settings.llm_api_key}"},
            json=payload,
            timeout=self.settings.llm_timeout_seconds,
        )
        if resp.status_code in (429, 500, 502, 503, 504):
            raise httpx.HTTPStatusError(
                f"LLM transient error {resp.status_code}", request=resp.request, response=resp
            )
        resp.raise_for_status()
        return resp.json()

    def _chat_json(self, messages: list[dict], max_tokens: int = 3000) -> dict:
        payload = {
            "model": self.settings.llm_model,
            "messages": messages,
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
            "max_tokens": max_tokens,
        }
        last_exc: Exception | None = None
        for attempt in range(3):
            try:
                content = self._post(payload)["choices"][0]["message"]["content"]
                return json.loads(_strip_fences(content))
            except (httpx.HTTPError, json.JSONDecodeError, KeyError, IndexError) as exc:
                last_exc = exc
                if attempt < 2:
                    time.sleep(2 * (attempt + 1))
        raise ProviderError(f"LLM request failed after retries: {last_exc}") from last_exc

    def plan_step(
        self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]
    ) -> AgentDecision:
        """One agent step: the model either calls tools or claims the goal is done."""

        payload = {
            "model": self.settings.llm_model,
            "messages": _sanitize_messages(messages),
            "tools": tools,
            "tool_choice": "auto",
            "temperature": 0.2,
            "max_tokens": self.settings.agent_max_tokens,
        }
        last_exc: Exception | None = None
        for attempt in range(3):
            try:
                data = self._post(payload)
                choice = data["choices"][0]
                return _parse_decision(
                    choice["message"], truncated=choice.get("finish_reason") == "length"
                )
            except (httpx.HTTPError, KeyError, IndexError, TypeError) as exc:
                last_exc = exc
                if attempt < 2:
                    time.sleep(2 * (attempt + 1))
        raise ProviderError(f"LLM agent step failed after retries: {last_exc}") from last_exc

    def summarize(self, messages: list[dict[str, Any]]) -> str:
        """Compress older transcript messages into a short factual summary."""

        transcript = "\n".join(
            f"{message.get('role')}: {str(message.get('content', ''))[:1500]}"
            for message in messages
        )
        payload = {
            "model": self.settings.llm_model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "把下面的 Agent 执行记录压缩成要点。保留已经得到的结论、涉及的文件路径、"
                        "问题编号和还没做完的事，不要复述原文，不要编造没有出现的信息。"
                    ),
                },
                {"role": "user", "content": transcript},
            ],
            "temperature": 0.2,
            "max_tokens": 800,
        }
        content = self._post(payload)["choices"][0]["message"]["content"]
        return str(content).strip()

    def parse(self, text: str, domain: str) -> ParsedRequirement:
        messages = [
            {"role": "system", "content": SYSTEM_PARSE},
            {"role": "user", "content": f"领域：{domain}\n需求文本：\n{text}"},
        ]
        for _ in range(2):
            raw = self._chat_json(messages)
            try:
                return ParsedRequirement.model_validate(raw)
            except ValidationError as exc:
                messages.append({"role": "assistant", "content": json.dumps(raw, ensure_ascii=False)})
                messages.append({"role": "user", "content": f"schema 校验失败：{exc}\n请只输出修正后的 JSON。"})
        raise ProviderError("LLM parse failed after repair")

    def review(self, role: str, parsed: ParsedRequirement, context: str) -> list[ReviewIssue]:
        messages = [
            {
                "role": "system",
                "content": ROLE_SYSTEM.get(role, ROLE_SYSTEM["product"])
                + "\n"
                + variant_prompt(self.settings.prompt_variant),
            },
            {
                "role": "user",
                "content": f"审查角色：{role}\n解析结果：\n{parsed.model_dump_json(indent=2)}\n原始需求：\n{context}",
            },
        ]
        for _ in range(2):
            raw = self._chat_json(messages, max_tokens=2000)
            try:
                items = raw.get("issues", raw if isinstance(raw, list) else [])
                issues = []
                for item in items:
                    item["role"] = role
                    issues.append(ReviewIssue.model_validate(item))
                return issues
            except ValidationError as exc:
                messages.append({"role": "assistant", "content": json.dumps(raw, ensure_ascii=False)})
                messages.append({"role": "user", "content": f"schema 校验失败：{exc}\n请只输出修正后的 JSON。"})
        raise ProviderError("LLM review failed after repair")

    def generate_prd(self, parsed: ParsedRequirement, domain: str, context: str) -> PRDDocument:
        schema_hint = """输出 JSON 对象，字段：
{"title": "...", "summary": "...", "background": "...", "target_users": ["..."],
 "functional_requirements": [{"id": "FR-1", "title": "...", "description": "...", "priority": "P0|P1|P2"}],
 "non_functional": ["..."], "permissions": ["..."],
 "data_model": [{"name": "...", "fields": [{"name": "...", "type": "string|number|date|enum", "required": true}]}],
 "pages": [{"id": "page-1", "title": "...", "description": "...", "components": ["form","table"], "states": ["default","empty","error"], "interactions": ["..."], "form_fields": [{"name":"...","label":"...","type":"text|number|select|date|textarea|checkbox","required":true,"options":[]}]}],
 "acceptance_criteria": ["..."], "open_questions": ["..."]}
"""
        messages = [
            {"role": "system", "content": "你是需求工程 Agent。根据解析结果生成结构化 PRD，只输出 JSON。" + schema_hint},
            {
                "role": "user",
                "content": f"领域：{domain}\n解析结果：\n{parsed.model_dump_json(indent=2)}\n原始需求：\n{context}",
            },
        ]
        for _ in range(2):
            raw = self._chat_json(messages, max_tokens=4000)
            try:
                return PRDDocument.model_validate(raw)
            except ValidationError as exc:
                messages.append({"role": "assistant", "content": json.dumps(raw, ensure_ascii=False)})
                messages.append({"role": "user", "content": f"schema 校验失败：{exc}\n请只输出修正后的 JSON。"})
        raise ProviderError("LLM PRD generation failed after repair")
