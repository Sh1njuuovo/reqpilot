"""Core domain models shared across the ReqPilot pipeline."""

from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field

Role = Literal["product", "frontend", "backend", "test"]
IssueCategory = Literal[
    "interaction", "logic", "permission", "data", "completeness", "consistency"
]
Severity = Literal["critical", "major", "minor", "suggestion"]
TaskType = Literal["frontend", "backend", "database", "test"]
Effort = Literal["S", "M", "L"]
SourceType = Literal["natural_language", "meeting_notes", "chat_history", "annotation"]
ProviderName = Literal["mock", "llm"]

REVIEW_ROLES: tuple[Role, ...] = ("product", "frontend", "backend", "test")


class RequirementInput(BaseModel):
    """Raw input from the user."""

    text: str = Field(min_length=1, description="Natural-language requirement text")
    domain: str = "generic"
    source: SourceType = "natural_language"


class DataField(BaseModel):
    name: str
    type: str = "string"
    required: bool = True
    note: str | None = None


class ParsedRequirement(BaseModel):
    """Schema-constrained extraction result."""

    background: str | None = None
    target_users: list[str] = Field(default_factory=list)
    user_stories: list[str] = Field(default_factory=list)
    functional_requirements: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    permissions: list[str] = Field(default_factory=list)
    data_fields: list[DataField] = Field(default_factory=list)
    exception_flows: list[str] = Field(default_factory=list)
    acceptance_criteria: list[str] = Field(default_factory=list)


class FunctionalRequirement(BaseModel):
    id: str
    title: str
    description: str
    priority: Literal["P0", "P1", "P2"] = "P1"


class DataEntity(BaseModel):
    name: str
    fields: list[DataField] = Field(default_factory=list)


class FormField(BaseModel):
    name: str
    label: str
    type: Literal["text", "number", "select", "date", "textarea", "checkbox"] = "text"
    required: bool = True
    options: list[str] = Field(default_factory=list)


class PRDPage(BaseModel):
    id: str
    title: str
    description: str = ""
    components: list[str] = Field(default_factory=list)
    states: list[str] = Field(default_factory=lambda: ["default"])
    interactions: list[str] = Field(default_factory=list)
    form_fields: list[FormField] = Field(default_factory=list)


class PRDDocument(BaseModel):
    title: str
    summary: str = ""
    background: str = ""
    target_users: list[str] = Field(default_factory=list)
    functional_requirements: list[FunctionalRequirement] = Field(default_factory=list)
    non_functional: list[str] = Field(default_factory=list)
    permissions: list[str] = Field(default_factory=list)
    data_model: list[DataEntity] = Field(default_factory=list)
    pages: list[PRDPage] = Field(default_factory=list)
    acceptance_criteria: list[str] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)


class ReviewIssue(BaseModel):
    id: str = ""
    role: Role
    roles: list[Role] = Field(default_factory=list)
    category: IssueCategory
    severity: Severity
    title: str
    description: str = ""
    evidence: list[str] = Field(default_factory=list)
    suggestion: str = ""
    dedup_key: str | None = None


class DevelopmentTask(BaseModel):
    id: str
    type: TaskType
    title: str
    description: str
    dependencies: list[str] = Field(default_factory=list)
    acceptance_criteria: list[str] = Field(default_factory=list)
    effort: Effort = "M"
    prd_refs: list[str] = Field(default_factory=list)


class Citation(BaseModel):
    doc_id: str
    section: str
    chunk: str


class StepTrace(BaseModel):
    step: str
    provider: str
    ok: bool
    duration_ms: int = 0
    fallback_used: bool = False
    error: str | None = None


class AgentRun(BaseModel):
    """Execution trace and evidence envelope for one pipeline run."""

    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    status: Literal["running", "succeeded", "failed", "needs_confirmation"] = "running"
    provider: ProviderName = "llm"
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None
    input_text_hash: str = ""
    steps: list[StepTrace] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    fallbacks: list[str] = Field(default_factory=list)
    fingerprint: str = ""

    @staticmethod
    def digest(text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
