from reqpilot.models import FormField, PRDDocument, PRDPage
from reqpilot.prototype import generate_prototype


def _prd(title="测试需求") -> PRDDocument:
    return PRDDocument(
        title=title,
        pages=[
            PRDPage(
                id="page-1",
                title="申请单",
                description="填写申请",
                components=["form", "table"],
                states=["default", "empty", "error", "loading"],
                interactions=["表单校验"],
                form_fields=[FormField(name="金额", label="金额", type="number", required=True)],
            )
        ],
    )


def test_prototype_contains_pages_and_states():
    html = generate_prototype(_prd(), offline=True)
    assert "<!doctype html>" in html.lower()
    assert 'id="page-1"' in html
    assert "class=\"state-empty" in html
    assert "cdn.tailwindcss.com" not in html


def test_prototype_escapes_injected_html():
    html = generate_prototype(_prd(title='<script>alert(1)</script>'), offline=True)
    assert "&lt;script&gt;" in html
    assert "<script>alert(1)</script>" not in html


def test_prototype_includes_tailwind_by_default():
    html = generate_prototype(_prd(), offline=False)
    assert "cdn.tailwindcss.com" in html
