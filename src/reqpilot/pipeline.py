"""LangGraph pipeline orchestrating parse → RAG → review → PRD → prototype → tasks."""

from __future__ import annotations

import hashlib
import json
import operator
import os
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Annotated, Any, TypedDict

from langgraph.graph import START, StateGraph
from langgraph.types import Send

from reqpilot.config import Settings
from reqpilot.models import (
    REVIEW_ROLES,
    AgentRun,
    Citation,
    ParsedRequirement,
    PRDDocument,
    RequirementInput,
    ReviewIssue,
    StepTrace,
)
from reqpilot.prd import render_markdown
from reqpilot.prototype import generate_prototype
from reqpilot.providers import ProviderError, get_provider
from reqpilot.rag import KnowledgeRetriever, build_retriever
from reqpilot.review.dedup import finalize_issues, prune_issues
from reqpilot.tasks import export_csv, export_json, export_markdown, split_tasks

SAMPLE_REQUIREMENT = """现有业务审批流程依赖线下沟通，效率低。系统面向审批管理员与普通业务人员，支持在线提交审批申请、多级审批流转、审批进度查询与历史记录导出。角色权限：管理员可配置审批流并查看全部数据，普通用户只能查看自己提交的记录。字段包括申请单编号、申请人、金额、审批状态、提交日期。必须支持幂等提交，防止重复申请；提交失败时自动重试；列表查询需要分页，超过 100 条分批加载。验收标准：管理员可完成审批流配置并生效，用户提交后可查询到进度，重复点击提交不会产生重复单据。"""
SAMPLE_DOMAIN = "approval"


class PipelineState(TypedDict, total=False):
    run: AgentRun
    input: RequirementInput
    parsed: ParsedRequirement
    knowledge: list[Citation]
    raw_issue_parts: Annotated[list[list[ReviewIssue]], operator.add]
    issues: list[ReviewIssue]
    issues_removed: int
    prd: PRDDocument
    tasks: list[Any]
    prototype_html: str
    prd_markdown: str
    tasks_markdown: str
    tasks_csv: str
    tasks_json: str
    step_traces: Annotated[list[StepTrace], operator.add]
    errors: Annotated[list[str], operator.add]
    fallbacks: Annotated[list[str], operator.add]
    raw_issue_count: int


@dataclass
class PipelineResult:
    run: AgentRun
    input_text: str = ""
    parsed: ParsedRequirement | None = None
    prd: PRDDocument | None = None
    issues: list[ReviewIssue] = field(default_factory=list)
    tasks: list[Any] = field(default_factory=list)
    prototype_html: str = ""
    prd_markdown: str = ""
    tasks_markdown: str = ""
    tasks_csv: str = ""
    tasks_json: str = ""
    citations: list[Citation] = field(default_factory=list)
    raw_issue_count: int = 0


def _duration(start: float) -> int:
    return int((time.monotonic() - start) * 1000)


class PipelineBuilder:
    def __init__(
        self,
        provider,
        retriever: KnowledgeRetriever | None = None,
        human_confirm: bool = False,
    ):
        self.provider = provider
        self.retriever = retriever
        self.human_confirm = human_confirm

    def _run_step(self, step_name: str, fn, key: str | None = None) -> dict[str, Any]:
        start = time.monotonic()
        try:
            result = fn()
            updates: dict[str, Any] = {
                "step_traces": [
                    StepTrace(
                        step=step_name,
                        provider=self.provider.name,
                        ok=True,
                        duration_ms=_duration(start),
                    )
                ]
            }
            if key:
                updates[key] = result
            return updates
        except Exception as exc:  # noqa: BLE001
            return {
                "step_traces": [
                    StepTrace(
                        step=step_name,
                        provider=self.provider.name,
                        ok=False,
                        duration_ms=_duration(start),
                        error=str(exc),
                    )
                ],
                "errors": [f"{step_name}: {exc}"],
            }

    def parse_node(self, state: PipelineState) -> dict[str, Any]:
        text = state["input"].text
        domain = state["input"].domain
        return self._run_step(
            "parse",
            lambda: self.provider.parse(text, domain),
            key="parsed",
        )

    def retrieve_node(self, state: PipelineState) -> dict[str, Any]:
        text = state["input"].text
        if self.retriever is None:
            return {
                "knowledge": [],
                "step_traces": [
                    StepTrace(step="retrieve", provider="none", ok=True, duration_ms=0)
                ],
            }

        def _search():
            parsed = state.get("parsed")
            query = text
            if parsed and parsed.functional_requirements:
                query = text + " " + " ".join(parsed.functional_requirements[:3])
            chunks = self.retriever.search(query, top_k=5)
            return [
                Citation(doc_id=c.doc_id, section=c.section, chunk=c.content)
                for c in chunks
            ]

        return self._run_step("retrieve", _search, key="knowledge")

    def fan_out_review(self, state: PipelineState) -> dict[str, Any]:
        # Routing to parallel review_one nodes happens via review_route (Send).
        return {}

    def review_route(self, state: PipelineState) -> list[Send]:
        parsed = state["parsed"]
        return [
            Send(
                "review_one",
                {
                    "role": role,
                    "parsed": parsed,
                    "context": state["input"].text,
                },
            )
            for role in REVIEW_ROLES
        ]

    def review_one(self, sub_state: dict[str, Any]) -> dict[str, Any]:
        role: str = sub_state["role"]
        parsed: ParsedRequirement = sub_state["parsed"]
        context: str = sub_state["context"]
        start = time.monotonic()
        try:
            issues = self.provider.review(role, parsed, context)
            trace = StepTrace(
                step=f"review:{role}",
                provider=self.provider.name,
                ok=True,
                duration_ms=_duration(start),
            )
            return {"raw_issue_parts": [issues], "step_traces": [trace]}
        except Exception as exc:  # noqa: BLE001
            return {
                "raw_issue_parts": [[]],
                "step_traces": [
                    StepTrace(
                        step=f"review:{role}",
                        provider=self.provider.name,
                        ok=False,
                        duration_ms=_duration(start),
                        error=str(exc),
                    )
                ],
                "errors": [f"review:{role}: {exc}"],
            }

    def merge_reviews(self, state: PipelineState) -> dict[str, Any]:
        parts = state.get("raw_issue_parts", [])
        raw = [issue for part in parts for issue in part]
        merged, removed = finalize_issues(raw)
        max_per_role = int(os.environ.get("REQPILOT_MAX_ISSUES_PER_ROLE", "5"))
        pruned = prune_issues(merged, max_per_role=max_per_role)
        for idx, issue in enumerate(pruned, start=1):
            issue.id = f"ISSUE-{idx:03d}"
        return {
            "issues": pruned,
            "issues_removed": removed + (len(merged) - len(pruned)),
            "raw_issue_count": len(raw),
        }

    def build_prd_node(self, state: PipelineState) -> dict[str, Any]:
        parsed = state["parsed"]
        domain = state["input"].domain
        context = state["input"].text
        return self._run_step(
            "generate_prd",
            lambda: self.provider.generate_prd(parsed, domain, context),
            key="prd",
        )

    def build_prototype_node(self, state: PipelineState) -> dict[str, Any]:
        prd = state["prd"]
        return {
            "prototype_html": generate_prototype(prd),
            "prd_markdown": render_markdown(prd),
            "step_traces": [
                StepTrace(step="prototype", provider="code", ok=True, duration_ms=0)
            ],
        }

    def split_tasks_node(self, state: PipelineState) -> dict[str, Any]:
        tasks = split_tasks(state["prd"])
        return {
            "tasks": tasks,
            "tasks_markdown": export_markdown(tasks),
            "tasks_csv": export_csv(tasks),
            "tasks_json": export_json(tasks),
            "step_traces": [
                StepTrace(step="tasks", provider="code", ok=True, duration_ms=0)
            ],
        }

    def finalize_node(self, state: PipelineState) -> dict[str, Any]:
        run: AgentRun = state["run"]
        run.steps = state.get("step_traces", [])
        run.citations = state.get("knowledge", [])
        run.errors = state.get("errors", [])
        run.fallbacks = state.get("fallbacks", [])
        run.completed_at = datetime.now(UTC)
        parsed = state.get("parsed")
        prd = state.get("prd")
        tasks = state.get("tasks")
        failed = parsed is None or prd is None or bool(run.errors)
        run.status = "failed" if failed or run.errors else "succeeded"
        canonical = json.dumps(
            {
                "parsed": parsed.model_dump() if parsed else None,
                "prd": prd.model_dump() if prd else None,
                "issues": [i.model_dump() for i in state.get("issues", [])],
                "tasks": [t.model_dump() for t in (tasks or [])],
            },
            ensure_ascii=False,
            sort_keys=True,
            default=str,
        )
        run.fingerprint = hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:32]
        run.input_text_hash = AgentRun.digest(state["input"].text)
        return {"run": run}

    def build(self):
        graph = StateGraph(PipelineState)
        graph.add_node("parse", self.parse_node)
        graph.add_node("retrieve", self.retrieve_node)
        graph.add_node("fan_out_review", self.fan_out_review)
        graph.add_node("review_one", self.review_one)
        graph.add_node("merge_reviews", self.merge_reviews)
        graph.add_node("build_prd", self.build_prd_node)
        graph.add_node("build_prototype", self.build_prototype_node)
        graph.add_node("split_tasks", self.split_tasks_node)
        graph.add_node("finalize", self.finalize_node)

        graph.add_edge(START, "parse")
        graph.add_conditional_edges(
            "parse",
            lambda state: "fail" if state.get("parsed") is None else "continue",
            {"continue": "retrieve", "fail": "finalize"},
        )
        graph.add_edge("retrieve", "fan_out_review")
        graph.add_conditional_edges("fan_out_review", self.review_route)
        graph.add_edge("review_one", "merge_reviews")
        graph.add_edge("merge_reviews", "build_prd")
        graph.add_edge("build_prd", "build_prototype")
        if self.human_confirm:
            graph.add_edge("build_prototype", "split_tasks")
            compiled = graph.compile(interrupt_before=["split_tasks"])
        else:
            graph.add_edge("build_prototype", "split_tasks")
            graph.add_edge("split_tasks", "finalize")
            compiled = graph.compile()
        return compiled


def run_pipeline(
    text: str,
    domain: str = SAMPLE_DOMAIN,
    provider_name: str = "llm",
    retriever_backend: str = "keyword",
    retriever: KnowledgeRetriever | None = None,
    knowledge_dir=None,
    human_confirm: bool = False,
    settings: Settings | None = None,
) -> PipelineResult:
    """Run the full pipeline and return the result envelope."""

    settings = settings or Settings.from_env()
    if provider_name not in ("mock", "llm"):
        raise ProviderError(f"unknown provider: {provider_name}")
    run = AgentRun(provider=provider_name, input_text_hash=AgentRun.digest(text))  # type: ignore[arg-type]
    provider = get_provider(provider_name, settings)

    if retriever is None:
        retriever = build_retriever(
            retriever_backend,
            knowledge_dir=knowledge_dir or settings.resolve_knowledge_dir(),
            vector_model=settings.vector_model,
        )

    builder = PipelineBuilder(provider, retriever=retriever, human_confirm=human_confirm)
    graph = builder.build()
    initial: PipelineState = {
        "run": run,
        "input": RequirementInput(text=text, domain=domain),
        "knowledge": [],
        "raw_issue_parts": [],
        "issues": [],
        "issues_removed": 0,
        "step_traces": [],
        "errors": [],
        "fallbacks": [],
        "raw_issue_count": 0,
    }
    final = graph.invoke(initial, config={"configurable": {"thread_id": run.id}})
    run = final["run"]
    if human_confirm:
        run.status = "needs_confirmation"
    return PipelineResult(
        run=run,
        input_text=text,
        parsed=final.get("parsed"),
        prd=final.get("prd"),
        issues=final.get("issues", []),
        tasks=final.get("tasks", []),
        prototype_html=final.get("prototype_html", ""),
        prd_markdown=final.get("prd_markdown", ""),
        tasks_markdown=final.get("tasks_markdown", ""),
        tasks_csv=final.get("tasks_csv", ""),
        tasks_json=final.get("tasks_json", ""),
        citations=final.get("knowledge", []),
        raw_issue_count=final.get("raw_issue_count", 0),
    )
