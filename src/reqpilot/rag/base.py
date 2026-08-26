"""Retriever protocol and shared types."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class RetrievedChunk:
    content: str
    doc_id: str
    section: str
    score: float

    def citation(self) -> str:
        return f"[{self.doc_id} / {self.section}]"


class RetrieverUnavailable(RuntimeError):
    """Raised when the requested backend cannot be initialized."""


class KnowledgeRetriever(Protocol):
    def search(self, query: str, top_k: int = 5) -> list[RetrievedChunk]:
        """Return chunks relevant to the query, ranked by score."""
