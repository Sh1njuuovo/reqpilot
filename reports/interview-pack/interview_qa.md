# ReqPilot 面试官拷问 Q&A

## 1. 项目为什么匹配 Agent 相关 HC？
需求工程本身是"多角色协作 + 工具调用 + 结构化交付"的典型 Agent 场景。ReqPilot 把 LLM 限定为解析与生成层，用 LangGraph 状态机编排流程、用 Pydantic 约束输出、用可插拔 RAG 注入领域知识、用评测集量化效果，覆盖 Agent 岗位最常考的四件事：编排、结构化、可靠性、可验证。

## 2. 输入输出是什么？主链路入口在哪？
输入是自然语言需求文本（可带领域与来源类型）。输出是 ParsedRequirement、多角色 ReviewIssue 列表、PRDDocument、单文件 HTML 原型、DevelopmentTask 列表（Markdown/CSV/JSON），以及 AgentRun 追踪（trace、citations、fingerprint）。入口有四个：CLI（`reqpilot smoke/demo/serve/eval`）、FastAPI（`POST /requirements`）、MCP server（`analyze_requirement` / `export_tasks`）、pytest。

## 3. LangGraph 图怎么设计的？为什么用它？
节点链：parse → retrieve → fan_out_review →（四路并行）review_one → merge_reviews → build_prd → build_prototype → split_tasks → finalize；parse 失败走条件边直达 finalize 标 failed。选 LangGraph 是因为：状态显式化、并行 Send 原语、interrupt 人工确认、每一步可 trace，比手写编排更可观测。

## 4. 四角色并行怎么实现的？踩过什么坑？
用 `Send` 做 fan-out：fan_out_review 节点返回空更新，真正路由写在 `add_conditional_edges` 返回 `[Send("review_one", {...})]`。踩坑：LangGraph 1.x 不允许普通节点直接返回 Send 列表，第一次实现时直接返回 Send，运行报 `InvalidUpdateError: Expected dict, got [Send(...)]`，改成 conditional edge 后解决。四个 review_one 通过 reducer（`operator.add`）把结果合并到 `raw_issue_parts`，merge 节点统一去重。

## 5. 多角色审查规则怎么设计的？mock 和 LLM 什么关系？
四个角色各有职责边界：产品查目标用户/验收/功能完整性，前端查页面与交互/表单校验/空异常态/角色差异，后端查数据字段/权限模型/幂等/分页，测试查异常路径/边界/可测试性。MockProvider 是确定性规则实现，OpenAICompatibleProvider 是同协议的 LLM 实现；两者共用同一套 Pydantic 输出 schema，所以评测可以跑两套对照。

## 6. LLM 输出不合 schema 怎么办？
两层容错：先让模型基于校验错误信息修复一次；仍失败则抛 ProviderError，管线捕获后落到确定性 MockProvider 的同一节点，并在 AgentRun 里记录 fallback 与原始错误。原则是"可靠性优先于效果"：任何一步失败都不会让整条链路挂掉。

## 7. RAG 怎么做的？为什么两个后端？
`KnowledgeRetriever` 协议统一返回带 doc_id/section/content 的 RetrievedChunk，注入解析与 PRD 生成上下文，并写进 AgentRun.citations 做引用追踪。默认 KeywordBackend 零依赖：CJK 一元/二元 token + 术语别名扩展，评测和 demo 不需要联网；VectorBackend 用 sentence-transformers 内存向量余弦相似度，需 `--extra vector`。生产可换 pgvector，接口不变。选型逻辑：演示环境离线可用 + 生产可升级，不把外部依赖变成门槛。

## 8. 问题去重怎么做？
按 `category + 规范化标题` 生成 dedup_key，跨角色同质问题合并（例如产品与测试都报"缺少验收标准"），保留最高严重度、合并证据与角色列表；之后统一分配 ISSUE 编号并按严重度排序。评测里 case-002 原始 2 条合并为 1 条，去重率 50%。

## 9. 原型生成器为什么是单 HTML？怎么验证？
一个 HTML 里按 page section 生成所有页面，导航切换 + 每页多状态区块 + 表单校验 JS + 深浅色切换，契合"快速探索多方案"的产品诉求，避免多文件工程成本。测试断言 HTML 结构、页面 id、状态区块，并用 `<script>` 注入用例验证转义，防 XSS。

## 10. 评测指标怎么算的？为什么 mock 和 LLM 数字差这么多？
12 条 golden 样例各带"必须抽到的字段组"和"预期问题标签 (role, category)"，标签按真人评审视角撰写（产品/前端/后端/测试会提的问题），和 mock 规则解耦。字段完整性 = 命中 golden 字段组比例；问题召回 = 检出 ∩ golden / golden；精确率 = 命中 / 检出；去重率 = (原始-最终)/原始。实测：LLM 完整性 100%（mock 86.1%）、召回 79.6%（mock 38.1%）、精确率 17.9%（mock 91.7%）。这个差距正好是项目想表达的设计：LLM 覆盖广但会过度标注，确定性规则精准但覆盖窄，评测把它们量化成了可讨论的取舍。

## 11. 真实 LLM 接入怎么考虑成本与延迟？
Provider 抽象下，LLM 只负责 parse/review/generate_prd 三个 JSON 输出，temperature 0.2、单次修复上限、超时 60s、失败回退 mock。生产可以加缓存（同输入 hash 命中）、并发控制、按角色批处理。当前评测 6ms 是 mock 的 CPU 数字，不代表 LLM 延迟。

## 12. 线上部署会怎么做？
知识库换 pgvector、运行状态持久化到 PostgreSQL、写操作引入 Redis+Celery 异步、原型用 Playwright 截图验证、trace 接 Langfuse/OpenTelemetry、任务导出走 MCP 白名单工具并保留人工确认节点。这些在 docs/design.md 的生产化备注里写明了，是演进路径，不是当前实现。

## 13. 最大限制是什么？下一步？
三个：领域泛化依赖知识库质量；当前评测基于 mock 与人工 golden，规模小（12 条）；版本差异（JSON Patch）和"需求到代码"未实现。下一步：扩 domain 样例集、把 LLM 两套 provider 的指标对比落进报告、实现版本差异与 MCP 写回任务平台。

## 14. 怎么证明不是套壳？
确定性约束 + 可复现证据：所有输出过 Pydantic schema；无 key 时 mock 全链路可跑；每次运行生成 input hash、fingerprint、step trace 与 citations；`reqpilot eval` 一键重跑所有指标；39 个测试锁行为。

## 15. 需求文本很口语、错别字、超长怎么办？
口语文本靠知识库术语别名（幂等=防重/重复提交）和宽松的规则分词兜底；超长文本按句/子句切分后分类，字段级合并进 ParsedRequirement；错别字是真实限制，mock 规则只能靠模糊 token 缓解，LLM provider 会显著更好——这也是双 provider 对照的意义。

## 16. 为什么状态用内存 + JSON 快照，不用数据库？
一期目标是本地可跑、可演示、可复现，数据库会抬高部署门槛；AgentRun 全量 JSON 快照已经满足审计与回放。生产演进路径写明换 PostgreSQL。主动讲这个取舍比被追问时支吾好。

## 17. 简历里的数字怎么复现？
`uv sync --extra dev && uv run reqpilot eval`（mock/keyword，报告在 reports/eval/eval_mock_keyword_latest.md）；`DEEPSEEK_API_KEY=... uv run reqpilot eval --provider llm`（LLM，eval_llm_keyword_latest.md）。完整性是 12 条 golden 字段组命中率平均；case-011（纯背景描述）为 0% 是设计内的"坏输入样例"。

## 18. 如果让你一个月把它做成产品，优先级？
先补版本差异与人工确认闭环（已留 interrupt 节点），再接 MCP 写回 Jira/GitLab 与 Playwright 截图，最后做领域知识库治理和真实 LLM 评测矩阵。原则：先保证"人审得住"，再谈自动化程度。
