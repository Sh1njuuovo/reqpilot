"""Single-file HTML prototype generator.

Each PRD page becomes a section in one self-contained HTML file with
Tailwind-based styling, multi-state toggles, form validation, and a light/dark
theme switch. `offline=True` skips the Tailwind CDN for hermetic tests.
"""

from __future__ import annotations

from html import escape

from reqpilot.models import PRDDocument


def _page_section(page) -> str:
    state_buttons = "".join(
        f'<button type="button" class="state-btn text-xs px-2 py-1 rounded border mr-1" '
        f'data-page="{escape(page.id)}" data-state="{escape(state)}">{escape(state)}</button>'
        for state in page.states
        if state != "default"
    )
    comps: list[str] = []
    for component in page.components:
        if component == "form":
            comps.append(_render_form(page))
        elif component == "table":
            comps.append(_render_table(page))
        else:
            comps.append(
                f'<div class="bg-white dark:bg-gray-800 rounded-lg shadow p-6 mb-4">'
                f'<div class="text-gray-500 dark:text-gray-400">组件：{escape(component)}</div>'
                f'<button type="button" class="mt-3 px-4 py-2 bg-blue-600 text-white rounded">操作按钮</button></div>'
            )
    interactions = "".join(
        f'<span class="inline-block bg-blue-50 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 '
        f'text-xs px-2 py-1 rounded mr-1 mb-1">{escape(i)}</span>'
        for i in page.interactions
    )
    return f"""
<section id="{escape(page.id)}" class="page hidden">
  <div class="bg-white dark:bg-gray-800 rounded-lg shadow p-6 mb-4">
    <h2 class="text-xl font-semibold mb-1">{escape(page.title)}</h2>
    <p class="text-gray-600 dark:text-gray-400 text-sm mb-3">{escape(page.description)}</p>
    {state_buttons}
  </div>
  {''.join(comps)}
  <div class="mb-4">{interactions}</div>
</section>"""


def _render_form(page) -> str:
    fields = "".join(
        f"""
    <div>
      <label class="block text-sm font-medium mb-1" for="{escape(page.id)}_{escape(f.name)}">
        {escape(f.label)}{' <span class="text-red-500">*</span>' if f.required else ''}
      </label>
      {_input_html(page, f)}
    </div>"""
        for f in page.form_fields
    )
    return f"""
<div class="bg-white dark:bg-gray-800 rounded-lg shadow p-6 mb-4">
  <h3 class="font-medium mb-3">表单</h3>
  <form id="form-{escape(page.id)}" onsubmit="return validateForm('{escape(page.id)}')" class="grid grid-cols-1 md:grid-cols-2 gap-4">
    {fields}
    <div class="md:col-span-2 flex gap-2">
      <button type="submit" class="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded">提交</button>
      <button type="reset" class="px-4 py-2 bg-gray-200 dark:bg-gray-700 rounded">重置</button>
    </div>
  </form>
  <p id="error-{escape(page.id)}" class="hidden text-red-600 text-sm mt-2"></p>
</div>"""


def _input_html(page, f) -> str:
    fid = f"{page.id}_{f.name}"
    required = "required" if f.required else ""
    if f.type == "select":
        opts = "".join(f'<option value="{escape(o)}">{escape(o)}</option>' for o in f.options)
        return f'<select id="{escape(fid)}" name="{escape(f.name)}" class="w-full rounded border px-3 py-2 bg-white dark:bg-gray-900 dark:border-gray-600">{opts}</select>'
    if f.type == "textarea":
        return f'<textarea id="{escape(fid)}" name="{escape(f.name)}" rows="3" {required} class="w-full rounded border px-3 py-2 bg-white dark:bg-gray-900 dark:border-gray-600"></textarea>'
    if f.type == "checkbox":
        return f'<input type="checkbox" id="{escape(fid)}" name="{escape(f.name)}" class="mt-2" {required}>'
    return f'<input type="{escape(f.type)}" id="{escape(fid)}" name="{escape(f.name)}" {required} class="w-full rounded border px-3 py-2 bg-white dark:bg-gray-900 dark:border-gray-600">'


def _render_table(page) -> str:
    sample = [
        ("示例记录 A", "2026-08-01", "处理中"),
        ("示例记录 B", "2026-08-12", "已完成"),
        ("示例记录 C", "2026-08-20", "待确认"),
    ]
    rows = "".join(
        f"<tr><td class='border px-3 py-2'>{escape(r[0])}</td>"
        f"<td class='border px-3 py-2'>{escape(r[1])}</td>"
        f"<td class='border px-3 py-2'>{escape(r[2])}</td></tr>"
        for r in sample
    )
    return f"""
<div class="bg-white dark:bg-gray-800 rounded-lg shadow p-6 mb-4">
  <h3 class="font-medium mb-3">列表</h3>
  <table class="w-full text-sm border-collapse">
    <thead><tr><th class="border px-3 py-2 text-left">名称</th><th class="border px-3 py-2 text-left">日期</th><th class="border px-3 py-2 text-left">状态</th></tr></thead>
    <tbody>{rows}</tbody>
  </table>
  <div class="state-empty hidden text-center py-8 text-gray-500">暂无数据</div>
  <div class="state-error hidden text-center py-8 text-red-500">加载失败，请稍后重试</div>
  <div class="state-loading hidden text-center py-8 text-gray-500">加载中…</div>
</div>"""


def generate_prototype(prd: PRDDocument, offline: bool = False) -> str:
    pages = "".join(_page_section(p) for p in prd.pages)
    nav_items = "".join(
        f'<button type="button" class="nav-btn px-3 py-2 text-sm rounded hover:bg-blue-50 '
        f'dark:hover:bg-blue-900/30" data-page="{escape(p.id)}">{escape(p.title)}</button>'
        for p in prd.pages
    )
    tailwind = (
        ""
        if offline
        else '<script src="https://cdn.tailwindcss.com"></script>'
    )
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(prd.title)} - 交互原型</title>
{tailwind}
</head>
<body class="bg-gray-100 text-gray-900 dark:bg-gray-900 dark:text-gray-100">
<header class="bg-white dark:bg-gray-800 border-b dark:border-gray-700 px-4 py-3 flex items-center justify-between sticky top-0 z-10">
  <div>
    <h1 class="text-lg font-bold">{escape(prd.title)}</h1>
    <p class="text-xs text-gray-500 dark:text-gray-400">单文件多页面交互原型 · 共 {len(prd.pages)} 个页面</p>
  </div>
  <button type="button" id="theme-toggle" class="px-3 py-1 text-sm rounded border">深色/浅色</button>
</header>
<nav class="bg-white dark:bg-gray-800 border-b dark:border-gray-700 px-4 py-2 flex gap-2 overflow-x-auto">
  {nav_items}
</nav>
<main class="max-w-4xl mx-auto p-4">
  {pages}
</main>
<script>
const pages = document.querySelectorAll('.page');
const navBtns = document.querySelectorAll('.nav-btn');
function showPage(id) {{
  pages.forEach(p => p.classList.add('hidden'));
  const target = document.getElementById(id);
  if (target) target.classList.remove('hidden');
  navBtns.forEach(b => b.classList.toggle('bg-blue-100', b.dataset.page === id));
}}
if (navBtns.length > 0) showPage(navBtns[0].dataset.page);
navBtns.forEach(b => b.addEventListener('click', () => showPage(b.dataset.page)));

function validateForm(pageId) {{
  const form = document.getElementById('form-' + pageId);
  const err = document.getElementById('error-' + pageId);
  const missing = Array.from(form.querySelectorAll('[required]')).filter(i => !i.value || i.value.trim() === '');
  if (missing.length > 0) {{
    err.textContent = '请填写必填项：' + missing.map(i => i.name || i.id).join('、');
    err.classList.remove('hidden');
    return false;
  }}
  err.classList.add('hidden');
  alert('提交成功（原型演示）');
  return false;
}}

document.querySelectorAll('.state-btn').forEach(b => b.addEventListener('click', () => {{
  const wrap = b.closest('section');
  wrap.querySelectorAll('.state-empty,.state-error,.state-loading').forEach(e => e.classList.add('hidden'));
  const target = wrap.querySelector('.state-' + b.dataset.state);
  if (target) target.classList.toggle('hidden');
}}));

document.getElementById('theme-toggle').addEventListener('click', () => {{
  document.body.classList.toggle('dark');
}});
</script>
</body>
</html>
"""
