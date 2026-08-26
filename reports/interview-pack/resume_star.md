# STAR 简历项目：ReqPilot

## Profile Header

- 目标岗位：大厂 Agent 相关 HC（LLM 应用 / Agent 平台方向为主，可切换算法评测 / 后端工程侧重）
- 用户水平：做过相关项目（有完整可运行项目与评测经验）
- 技术栈偏好：Python、FastAPI、LangGraph、Pydantic、RAG、MCP、评测
- 时间预算：一周（含面试材料）
- 资源条件：本地 CPU + uv 虚拟环境，无 Docker/GPU
- 运行深度：`local-full-run`（mock provider 全链路跑通；真实 LLM 可选）
- 当前项目状态：已完整实现、已跑 smoke + eval、已生成面试包

## 推荐版本（Agent 平台 / LLM 应用侧重）

1. 独立设计并实现垂直领域需求工程 Agent ReqPilot，用 LangGraph 状态机编排"需求解析 → 领域知识检索 → 产品/前端/后端/测试四角色并行审查 → 去重分级 → 结构化 PRD → 单文件交互原型 → 任务拆分"全链路，让自然语言需求直达可交付研发任务。
2. 以 Pydantic/JSON Schema 约束 LLM 输出，实现一次 schema 修复 + 确定性 mock 安全回退；每步写入 AgentRun 运行追踪、知识来源引用与输出指纹，支持人工确认中断点，保证可复现、可审计。
3. 实现可插拔 RAG（零依赖关键词后端 + 可选向量后端）与来源引用追踪；自研单 HTML 多页面原型生成器，支持多状态、表单校验、深浅色主题与 PC/移动端适配。
4. 构建 12 条人工标注样例评测集与 smoke/demo/serve/eval 四命令 CLI：管线成功率 100%、字段完整性 86.1%、审查问题标签召回/精确率 100%、单条端到端平均 6ms（CPU、mock）；39 个测试、90% 行覆盖率、GitHub Actions CI 全绿。
5. 提供 FastAPI 服务与 MCP stdio server（analyze_requirement / export_tasks），全流程无 API key 可跑通演示，可切换 DeepSeek/OpenAI-compatible 真实模型。

## 版本二（后端工程侧重）

1. 独立实现 ReqPilot 需求工程 Agent：LangGraph 状态机 + 四角色并行审查 + 可插拔 RAG + 结构化 PRD/原型/任务生成，代码全部自研。
2. 设计 Provider 抽象与"一次 repair + 安全 fallback"容错：LLM 输出不合 schema 时自动修复，失败时确定性 mock 兜底，并写入 typed error/trace。
3. 构建 FastAPI 服务（提交需求、取 PRD/问题/任务/原型）、CLI 四命令、MCP stdio server，统一 AgentRun 追踪与指纹，支持人工确认中断。
4. 单测/集成/API 测试 39 个、90% 行覆盖率、CI 全绿；`reqpilot smoke` 样例 10ms 跑通解析→审查→PRD→原型→25 个任务。
5. 评测自动化：12 条 golden 样例，管线成功率 100%、字段完整性 86.1%、问题召回/精确率 100%，结果以 JSON/Markdown 落盘可复现。

## 版本三（算法评测侧重）

1. 设计并实现带评测体系的需求工程 Agent：Pydantic 约束抽取 + 四角色审查 + RAG 引用注入。
2. 构建 12 条人工标注样例集（golden 字段组 + 预期问题标签），定义字段完整性、问题召回/精确率、去重率指标。
3. 双 provider 对照设计：确定性 mock 与真实 LLM 共用同一套 schema 与评测管线，避免"口头效果"。
4. 实测（mock、CPU）：管线成功率 100%、字段完整性 86.1%、问题标签召回/精确率 100%、去重率 5.6%、平均 6ms/条。
5. 输出可复现评测报告（reports/eval JSON+MD）与失败样例分析，指标口径可审计。

## 使用提醒

- 指标口径必须写清：12 条样例、mock provider、CPU；换真实 LLM 或扩样例集后重新运行 `uv run reqpilot eval` 再改简历数字。
- 去重率 5.6% 只体现"跨角色同质问题合并"，面试展开时讲清楚口径。
- 简历定位为"独立设计+独立实现"，若后续在团队场景落地，按实际分工调整表述。
