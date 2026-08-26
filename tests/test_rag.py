from reqpilot.rag import KeywordBackend
from reqpilot.rag.knowledge import KnowledgeBase, KnowledgeDoc, KnowledgeSection, load_knowledge


def _kb() -> KnowledgeBase:
    return KnowledgeBase(
        docs=[
            KnowledgeDoc(
                id="approval-flow",
                title="审批流",
                sections=[KnowledgeSection(name="幂等约定", content="所有创建类接口必须支持幂等键，重复提交不产生重复单据。")],
            ),
            KnowledgeDoc(
                id="interface",
                title="接口约定",
                sections=[KnowledgeSection(name="分页约定", content="列表接口必须支持分页参数，默认每页 20 条。")],
            ),
        ],
        terms={"幂等": ["防重", "重复提交"]},
    )


def test_keyword_retriever_finds_matching_doc():
    backend = KeywordBackend(_kb())
    hits = backend.search("重复提交会不会产生重复单据", top_k=2)
    assert hits
    assert hits[0].doc_id == "approval-flow"
    assert hits[0].section == "幂等约定"
    assert hits[0].score > 0


def test_keyword_retriever_returns_citations():
    backend = KeywordBackend(_kb())
    hits = backend.search("列表分页", top_k=1)
    assert hits and hits[0].doc_id == "interface"
    assert "分页约定" in hits[0].citation()


def test_load_knowledge_missing_path_empty():
    kb = load_knowledge("/nonexistent/domain.json")
    assert kb.docs == []
