"""Runtime configuration, resolved from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def project_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


@dataclass(frozen=True)
class Settings:
    llm_base_url: str = "https://api.deepseek.com/v1"
    llm_model: str = "deepseek-chat"
    llm_api_key: str | None = None
    llm_timeout_seconds: float = 60.0
    knowledge_dir: Path = Path("eval/knowledge")
    vector_model: str = "all-MiniLM-L6-v2"

    @classmethod
    def from_env(cls) -> Settings:
        return cls(
            llm_base_url=os.getenv(
                "REQPILOT_LLM_BASE_URL",
                os.getenv("OPENAI_BASE_URL", "https://api.deepseek.com/v1"),
            ),
            llm_model=os.getenv("REQPILOT_LLM_MODEL", "deepseek-chat"),
            llm_api_key=os.getenv("DEEPSEEK_API_KEY") or os.getenv("OPENAI_API_KEY"),
            knowledge_dir=Path(os.getenv("REQPILOT_KNOWLEDGE_DIR", "eval/knowledge")),
            vector_model=os.getenv("REQPILOT_VECTOR_MODEL", "all-MiniLM-L6-v2"),
        )

    def resolve_knowledge_dir(self) -> Path:
        p = self.knowledge_dir
        if not p.is_absolute():
            p = project_root() / p
        return p
