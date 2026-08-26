"""Knowledge base loading and representation."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class KnowledgeSection:
    name: str
    content: str


@dataclass(frozen=True)
class KnowledgeDoc:
    id: str
    title: str
    sections: list[KnowledgeSection] = field(default_factory=list)


@dataclass
class KnowledgeBase:
    docs: list[KnowledgeDoc] = field(default_factory=list)
    terms: dict[str, list[str]] = field(default_factory=dict)

    def alias_lookup(self, token: str) -> list[str]:
        """Return canonical terms whose aliases contain the token."""

        hits = []
        for term, aliases in self.terms.items():
            if token == term or token in aliases:
                hits.append(term)
        return hits


def load_knowledge(path: str | Path | None) -> KnowledgeBase:
    """Load knowledge from a JSON file: {"terms": {...}, "docs": [...]}."""

    if path is None:
        return KnowledgeBase()
    p = Path(path)
    if p.is_dir():
        candidates = sorted(p.glob("*.json"))
        if not candidates:
            return KnowledgeBase()
        p = candidates[0]
    if not p.exists():
        return KnowledgeBase()
    data = json.loads(p.read_text(encoding="utf-8"))
    docs = [
        KnowledgeDoc(
            id=d.get("id", f"doc-{i}"),
            title=d.get("title", ""),
            sections=[
                KnowledgeSection(name=s.get("name", ""), content=s.get("content", ""))
                for s in d.get("sections", [])
            ],
        )
        for i, d in enumerate(data.get("docs", []))
    ]
    return KnowledgeBase(docs=docs, terms=data.get("terms", {}))
