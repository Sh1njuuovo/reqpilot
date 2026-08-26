"""Zero-dependency keyword retriever with term expansion."""

from __future__ import annotations

import re
from collections import Counter

from reqpilot.rag.base import RetrievedChunk
from reqpilot.rag.knowledge import KnowledgeBase

CJK_RE = re.compile(r"[\u4e00-\u9fff]+")
ASCII_RE = re.compile(r"[a-z0-9]+")


def _tokens(text: str) -> Counter[str]:
    text = text.lower()
    counter: Counter[str] = Counter()
    for word in ASCII_RE.findall(text):
        counter[word] += 1
    for seg in CJK_RE.findall(text):
        if len(seg) == 1:
            counter[seg] += 1
        else:
            for i in range(len(seg)):
                counter[seg[i]] += 1
            for i in range(len(seg) - 1):
                counter[seg[i : i + 2]] += 1.5
    return counter


class KeywordBackend:
    """Scores chunks by token overlap with query, boosted by term aliases."""

    def __init__(self, knowledge: KnowledgeBase):
        self.knowledge = knowledge
        self._index: list[tuple[Counter[str], str, str, str]] = []
        for doc in knowledge.docs:
            for section in doc.sections:
                self._index.append(
                    (
                        _tokens(section.content),
                        section.content,
                        doc.id,
                        section.name,
                    )
                )

    def _query_tokens(self, query: str) -> Counter[str]:
        q = _tokens(query)
        for token in list(q):
            for term in self.knowledge.alias_lookup(token):
                q[term] += 2.0
        return q

    def search(self, query: str, top_k: int = 5) -> list[RetrievedChunk]:
        q = self._query_tokens(query)
        scored: list[tuple[float, str, str, str]] = []
        for tokens, content, doc_id, section in self._index:
            overlap = sum(count for token, count in q.items() if tokens[token])
            if overlap <= 0:
                continue
            scored.append((overlap, content, doc_id, section))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [
            RetrievedChunk(content=content, doc_id=doc_id, section=section, score=score)
            for score, content, doc_id, section in scored[:top_k]
        ]
