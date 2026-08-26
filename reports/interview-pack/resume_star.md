# STAR 简历项目：ReqPilot

## Profile Header

- 目标岗位：大厂 Agent 相关 HC（LLM 应用 / Agent 平台方向为主，可切换算法评测 / 后端工程侧重）
- 用户水平：做过相关项目（有完整可运行项目与评测经验）
- 技术栈偏好：Python、FastAPI、LangGraph、Pydantic、RAG、MCP、LLM 评测
- 时间预算：一周（含面试材料）
- 资源条件：本地 CPU + uv 虚拟环境 + DeepSeek API
- 运行深度：`local-full-run`（真实 LLM 全链路跑通）
- 当前项目状态：已完整实现、已跑真实 LLM smoke + eval、已生成面试包

## 推荐版本（Agent 平台 / LLM 应用侧重）

1. 独立设计并实现 LLM 驱动的垂直领域需求工程 Agent ReqPilot，用 LangGraph 状态机编排"需求解析 → 领域知识检索 → 产品/前端/后端/测试四角色并行审查 → 去重与严重度收敛 → 结构化 PRD → 单文件交互原型 → 任务拆分"全链路。
2. 以 Pydantic/JSON Schema 约束 LLM 输出，实现一次 schema 修复 + 指数退避重试 + typed error 追踪，失败时明确标记 run 为 failed、不产出伪结果；每步写入 AgentRun 追踪、知识引用与输出指纹，支持人工确认中断。
3. 面向 LLM 输出设计收敛护栏：跨角色同质问题去重 + 每角色按严重度保留 Top-5，解决模型过度标注，让审查列表保持可人工审阅；RAG 检索可插拔（关键词/向量），带来源引用追踪。
4. 构建 12 条人工评审视角样例评测集：DeepSeek 实测管线成功率 100%、字段完整性 100%、问题召回 86.5%、单条平均 18.9s；39 个测试、90% 行覆盖率、GitHub Actions CI 全绿。
5. 提供 FastAPI 服务与 MCP stdio server（analyze_requirement / export_tasks），全流程真实 LLM 可跑通演示。

## 版本二（后端工程侧重）

1. 独立实现 ReqPilot 需求工程 Agent：LangGraph 状态机 + 四角色并行审查 + 可插拔 RAG + 结构化 PRD/原型/任务生成，LLM 为唯一执行引擎。
2. 设计 LLM 可靠性管线：Pydantic 结构化输出 + 一次修复 + 3 次退避重试 + typed error trace；问题去重与每角色 Top-5 收敛，输出可审阅。
3. 构建 FastAPI 服务、CLI 四命令、MCP stdio server，统一 AgentRun 追踪与指纹，支持人工确认中断。
4. 单测/集成/API 测试 39 个、90% 行覆盖率、CI 全绿；真实 LLM 样例端到端跑通。
5. 评测自动化：12 条人工评审标准样例，管线成功率 100%、字段完整性 100%、问题召回 86.5%，报告 JSON/Markdown 落盘可复现。

## 版本三（算法评测侧重）

1. 设计并实现带评测体系的 LLM 需求工程 Agent：Pydantic 约束抽取 + 四角色 LLM 审查 + RAG 引用注入。
2. 构建 12 条人工评审视角样例集（golden 字段组 + 预期问题标签，与实现规则解耦），定义字段完整性、问题召回、去重率指标。
3. 实测（DeepSeek-chat）：管线成功率 100%、字段完整性 100%、问题召回 86.5%；同时量化模型过度标注（粗粒度标签精确率约 19%），作为收敛护栏设计的动机。
4. 输出可复现评测报告（reports/eval JSON+MD）与逐条问题明细，指标口径可审计。

## 使用提醒

- 指标口径必须写清：12 条样例、golden 为人工评审视角、DeepSeek-chat 实测；扩样例集或换模型后重新运行 `uv run reqpilot eval` 再改简历数字。
- 精确率约 19% 是粗粒度 (角色,类别) 标签命中率，主动讲成"模型过度标注 → 需要护栏"的工程动机，别回避。
- 简历定位为"独立设计+独立实现"，若后续在团队场景落地，按实际分工调整表述。
