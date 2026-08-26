# ReqPilot 30 分钟 Demo 脚本

前置：`export DEEPSEEK_API_KEY=... && uv sync --extra dev && uv run reqpilot demo`，产物在 `reports/demo/`。

## 0-3 分钟：定位与一句话
"这是一个 LLM 驱动的需求工程 Agent：自然语言需求进去，结构化 PRD、四角色审查报告、可点击原型、研发任务出来。LLM 负责理解和生成，编排、校验与收敛由工程层保证。"

## 3-8 分钟：跑一遍全链路（reports/demo/summary.json）
执行 `uv run reqpilot smoke`，指着 summary 讲：解析出的功能需求/字段、审查问题（已去重收敛）、页面数、任务数。强调每个环节都是真实 LLM 输出 + Pydantic 校验。

## 8-15 分钟：多角色审查（reports/demo/issues.json）
挑 3 条问题讲：产品"缺少验收标准"、前端"表单缺少校验规则"、后端"写操作缺少幂等性设计"——对应四角色职责；再讲收敛护栏：跨角色同质问题合并、每角色保留 Top-5，保证列表可人审。

## 15-22 分钟：PRD + 原型（reports/demo/prd.md / prototype.html）
打开 prototype.html：单 HTML 多页面、空/错误/加载状态、表单必填校验、深浅色。回到 prd.md 讲"结构化数据 → 模板渲染"，页面与功能需求一一对应。

## 22-27 分钟：任务拆分 + 评测（reports/demo/tasks.md / reports/eval/eval_llm_keyword_latest.md）
tasks.md 讲依赖关系（backend → frontend → test）。评测页讲口径：12 条人工评审标准样例，DeepSeek 实测成功率 100%、完整性 100%、召回 86.5%、18.9s/条；主动讲精确率低 = 模型过度标注，收敛护栏就是为此设计的。

## 27-30 分钟：架构图 + 收尾
画 LangGraph 节点链与四角色并行，讲一个失败 case（LLM 批量限流 → 加退避重试恢复 100%），收尾讲生产路径（pgvector/MCP/人工确认）与下一步（版本差异、更大规模评测）。
