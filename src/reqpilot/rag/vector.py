"""Optional sentence-transformer vector backend (requires the 'vector' extra)."""

from __future__ import annotations

from reqpilot.rag.base import RetrievedChunk, RetrieverUnavailable
from reqpilot.rag.knowledge import KnowledgeBase


class VectorBackend:
    """In-memory embeddings + cosine similarity."""

    def __init__(self, knowledge: KnowledgeBase, model_name: str = "all-MiniLM-L6-v2"):
        try:
            import numpy as np  # noqa: F401
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise RetrieverUnavailable(
                "vector backend requires `uv sync --extra vector` and a model download"
            ) from exc
        self.model = SentenceTransformer(model_name)
        self._chunks: list[tuple[str, str, str]] = []  # content, doc_id, section
        texts = []
        for doc in knowledge.docs:
            for section in doc.sections:
                self._chunks.append((section.content, doc.id, section.name))
                texts.append(section.content)
        self._embeddings = self.model.encode(texts, normalize_embeddings=True) if texts else []

    def search(self, query: str, top_k: int = 5) -> list[RetrievedChunk]:
        import numpy as np

        if not self._chunks:
            return []
        q = self.model.encode([query], normalize_embeddings=True)[0]
        sims = np.asarray(self._embeddings) @ q
        order = np.argsort(-sims)[:top_k]
        return [
            RetrievedChunk(
                content=self._chunks[i][0],
                doc_id=self._chunks[i][1],
                section=self._chunks[i][2],
                score=float(sims[i]),
            )
            for i in order
            if sims[i] > 0
        ]
