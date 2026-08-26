"""Retrieval layer: pluggable keyword / vector backends with citation tracking."""

from __future__ import annotations

from reqpilot.rag.base import KnowledgeRetriever, RetrievedChunk, RetrieverUnavailable
from reqpilot.rag.keyword import KeywordBackend
from reqpilot.rag.knowledge import KnowledgeBase, load_knowledge
from reqpilot.rag.vector import VectorBackend

__all__ = [
    "KeywordBackend",
    "KnowledgeBase",
    "KnowledgeRetriever",
    "RetrievedChunk",
    "RetrieverUnavailable",
    "VectorBackend",
    "load_knowledge",
]


def build_retriever(
    backend: str = "keyword",
    knowledge: KnowledgeBase | None = None,
    knowledge_dir=None,
    vector_model: str = "all-MiniLM-L6-v2",
) -> KnowledgeRetriever:
    """Build a retriever; defaults to the zero-dependency keyword backend."""

    if knowledge is None:
        knowledge = load_knowledge(knowledge_dir)
    if backend == "keyword":
        return KeywordBackend(knowledge)
    if backend == "vector":
        return VectorBackend(knowledge, model_name=vector_model)
    raise RetrieverUnavailable(f"unknown retriever backend: {backend}")
