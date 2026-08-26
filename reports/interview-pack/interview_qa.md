# ReqPilot 面试官拷问 Q&A

## 1. 项目为什么匹配 Agent 相关 HC？
需求工程本身是"多角色协作 + 工具调用 + 结构化交付"的典型 Agent 场景。ReqPilot 用 LLM 做理解和生成，用 LangGraph 编排流程、Pydantic 约束输出、RAG 注入领域知识、评测集量化效果，覆盖 Agent 岗位最常考的四件事：编排、结构化、可靠性、可验证。

## 2. 输入输出是什么？主链路入口在哪？
输入是自然语言需求文本（可带领域与来源类型）。输出是 ParsedRequirement、多角色 ReviewIssue 列表（已去重收敛）、PRDDocument、单文件 HTML 原型、DevelopmentTask 列表（Markdown/CSV/JSON），以及 AgentRun 追踪（trace、citations、fingerprint）。入口有四个：CLI（`reqpilot smoke/demo/serve/eval`）、FastAPI（`POST /requirements`）、MCP server（`analyze_requirement` / `export_tasks`）、pytest。

## 3. LangGraph 图怎么设计的？为什么用它？
节点链：parse → retrieve → fan_out_review →（四路并行）review_one → merge_reviews（去重+收敛）→ build_prd → build_prototype → split_tasks → finalize；parse 失败走条件边直达 finalize 标 failed。选 LangGraph：状态显式化、并行 Send 原语、interrupt 人工确认、每步可 trace。

## 4. 四角色并行怎么实现的？踩过什么坑？
用 `Send` 做 fan-out：fan_out_review 节点返回空更新，路由写在 `add_conditional_edges` 返回 `[Send("review_one", {...})]`。踩坑：LangGraph 1.x 不允许普通节点直接返回 Send 列表，第一次实现报 `InvalidUpdateError: Expected dict, got [Send(...)]`，改成 conditional edge 后解决。四个 review_one 通过 reducer 合并到 `raw_issue_parts`，merge 节点统一去重。

## 5. 多角色审查提示词怎么设计的？怎么避免四个角色各说各话？
四个角色各有职责边界：产品查目标用户/验收/流程，前端查页面/交互/状态/校验，后端查接口/数据/权限/幂等/分页，测试查边界/异常/可测试性。提示词要求"合并同类、每角色最多 5 条、宁缺毋滥"，输出统一走 Pydantic schema；后处理再做跨角色去重和按严重度收敛，保证列表可审阅。

## 6. LLM 输出不合 schema 或调用失败怎么办？
三层容错：校验失败给模型一次基于错误信息的修复机会；网络/瞬时错误指数退避重试 3 次；仍失败则记录 typed error 并把 run 标记 failed。原则是"不产出伪结果"——宁可失败也不拿假内容顶替。

## 7. RAG 怎么做的？为什么两个后端？
`KnowledgeRetriever` 协议统一返回带 doc_id/section/content 的 RetrievedChunk，注入解析与 PRD 生成上下文，并写进 AgentRun.citations 做引用追踪。默认 KeywordBackend 零依赖（CJK token + 术语别名扩展），VectorBackend 用 sentence-transformers 内存向量，生产可换 pgvector，接口不变。

## 8. 问题去重和收敛怎么做？
按 `category + 规范化标题` 合并跨角色同质问题（例如产品与测试都报"缺少验收标准"），保留最高严重度并合并角色证据；随后按严重度每角色保留 Top-5（`REQPILOT_MAX_ISSUES_PER_ROLE` 可配），最后重新编号。这直接解决 LLM 过度标注问题。

## 9. 原型生成器为什么是单 HTML？怎么验证？
一个 HTML 里按 page section 生成所有页面：导航切换 + 多状态区块 + 表单校验 JS + 深浅色切换，契合"快速探索多方案"的诉求。测试断言 HTML 结构、页面 id、状态区块，并用 `<script>` 注入用例验证转义防 XSS。

## 10. 评测指标怎么算的？为什么精确率只有 19% 但你还敢写？
12 条 golden 样例各带"必须抽到的字段组"和"预期问题标签 (role, category)"，标签按真人评审视角撰写。字段完整性 = 命中 golden 字段组比例；问题召回 = 检出 ∩ golden / golden；精确率 = 命中 / 检出。实测（DeepSeek）：成功率 100%、完整性 100%、召回 86.5%、平均 18.9s/条。精确率低是因为模型会输出大量额外问题，粗粒度标签命中率自然被稀释——这恰好是收敛护栏存在的动机，也是评测设计的一部分：先量化，再治理。

## 11. 真实 LLM 接入怎么考虑成本与延迟？
LLM 只负责 parse/review/generate_prd 三个 JSON 输出，temperature 0.2、单次修复、3 次退避重试、超时 60s。生产可加缓存（输入 hash 命中）、并发控制、按角色批处理。当前 18.9s/条是 DeepSeek 实测网络延迟，不是 CPU 计算。

## 12. 线上部署会怎么做？
知识库换 pgvector、运行状态持久化 PostgreSQL、写操作引入 Redis+Celery 异步、原型用 Playwright 截图验证、trace 接 Langfuse/OpenTelemetry、任务导出走 MCP 白名单工具并保留人工确认节点。演进路径写在 docs/design.md。

## 13. 最大限制是什么？下一步？
三个：领域泛化依赖知识库质量；评测规模小（12 条）且 golden 为人工撰写；版本差异（JSON Patch）和"需求到代码"未实现。下一步：扩 domain 样例集、加 LLM-as-judge 的问题有效性抽样评测、实现版本差异与 MCP 写回任务平台。

## 14. 怎么证明不是套壳？
LLM 是唯一执行引擎，所有输出过 Pydantic schema；每次运行生成 input hash、fingerprint、step trace 与 citations；`reqpilot eval` 一键重跑 12 条样例的全部指标；测试用确定性替身锁行为，不依赖网络；失败路径有 typed error 追踪。

## 15. 需求文本很口语、错别字、超长怎么办？
口语和错别字是 LLM 的主场，提示词里明确要求结合领域术语（知识库别名）理解；超长文本先按句/子句切分再抽取，字段级合并进 ParsedRequirement；对特别长的输入可以分块多次解析后合并（下一步计划）。

## 16. 为什么状态用内存 + JSON 快照，不用数据库？
一期目标是本地可跑、可演示、可复现，数据库会抬高部署门槛；AgentRun 全量 JSON 快照已满足审计与回放。生产演进路径写明换 PostgreSQL。主动讲取舍比被追问时支吾好。

## 17. 简历里的数字怎么复现？
`export DEEPSEEK_API_KEY=... && uv run reqpilot eval`，报告在 reports/eval/eval_llm_keyword_latest.md。完整性是 12 条 golden 字段组命中率平均；case-011（纯背景描述）为 0% 是设计内的"坏输入样例"。

## 18. 如果让你一个月把它做成产品，优先级？
先补版本差异与人工确认闭环（已留 interrupt 节点），再接 MCP 写回 Jira/GitLab 与 Playwright 截图，最后做知识库治理和更大规模的评测（含 LLM-as-judge 有效性抽样）。原则：先保证"人审得住"，再谈自动化程度。
