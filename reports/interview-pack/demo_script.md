# ReqPilot 30 分钟 Demo 脚本

前置：`uv sync --extra dev && uv run reqpilot demo`，产物在 `reports/demo/`。

## 0-3 分钟：定位与一句话
"这是一个需求工程 Agent：自然语言需求进去，结构化 PRD、多角色审查报告、可点击原型、研发任务出来。核心思路是 LLM 只负责理解和生成，流程与质量由确定性代码保证。"

## 3-8 分钟：跑一遍全链路（reports/demo/summary.json）
执行 `uv run reqpilot smoke`，指着 summary 讲：8 个功能需求、4 个数据字段、5 条审查问题、8 个页面、25 个任务，10ms 跑完（mock）。强调"没有 API key 也能跑"。

## 8-15 分钟：多角色审查（reports/demo/issues.json）
挑 3 条问题讲：产品"建议补充用户故事"、前端"表单缺少校验规则"、后端"写操作缺少幂等性设计"——对应"AI = 产品+前端+后端+测试"的四个视角，再说去重：产品和测试同时报"缺少验收标准"会合并成一条，保留两个角色证据。

## 15-22 分钟：PRD + 原型（reports/demo/prd.md / prototype.html）
打开 prototype.html：讲单 HTML 多页面、空/错误/加载状态切换、表单必填校验、深浅色。回到 prd.md 讲"结构化数据 → 模板渲染"，页面信息架构与功能需求一一对应。

## 22-27 分钟：任务拆分 + 评测（reports/demo/tasks.md / reports/eval/eval_mock_latest.md）
tasks.md 讲依赖关系（backend → frontend → test）。评测页讲口径：12 条 golden 样例、成功率 100%、完整性 86.1%、召回/精确率 100%、6ms/条，强调"这些数字是 mock 与标注集的一致性命中，接 LLM 必须重跑"。

## 27-30 分钟：架构图 + 收尾
画 LangGraph 节点链与并行审查，讲一个失败 case（Send 必须走 conditional edge），收尾讲生产路径（pgvector/MCP/人工确认）与下一步（版本差异、真实 LLM 评测矩阵）。
