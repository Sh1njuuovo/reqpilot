# ReqPilot 核心代码讲解稿

## 1. 入口

- CLI：`src/reqpilot/cli.py`，四个子命令 smoke/demo/serve/eval。
- API：`src/reqpilot/api.py`，`POST /requirements` 触发一次完整管线，其余 GET 端点取 PRD/问题/任务/原型。
- MCP：`src/reqpilot/mcp_server.py`，stdio 暴露 `analyze_requirement`、`export_tasks`。
- 测试入口：`tests/test_pipeline.py` 端到端。

## 2. 配置

`src/reqpilot/config.py` 的 `Settings.from_env()`：`DEEPSEEK_API_KEY`/`OPENAI_API_KEY`、`REQPILOT_LLM_BASE_URL`、`REQPILOT_LLM_MODEL`、`REQPILOT_KNOWLEDGE_DIR`。默认 mock provider，不需要任何环境变量。

## 3. 核心输入输出

- 输入：`RequirementInput{text, domain, source}`。
- 中间：`ParsedRequirement`（10 组字段）、`RetrievedChunk`（content/doc_id/section/score）。
- 输出：`ReviewIssue{role,category,severity,evidence,suggestion}`、`PRDDocument{functional_requirements,pages,data_model,...}`、`DevelopmentTask{type,dependencies,effort}`、`AgentRun{steps,citations,fingerprint}`。

## 4. 核心模块

### providers/mock.py
确定性规则解析器：句子级抽取用户故事/目标用户，子句级按优先级分类（背景 > 权限 > 约束 > 异常 > 验收 > 字段 > 功能）；四角色审查各自实现规则集合；PRD 由"结构化数据 → 模板"生成。

### pipeline.py（重点）
`PipelineBuilder` 用 LangGraph 组装 9 个节点；`_run_step` 统一做计时、trace、异常捕获与 mock fallback；`review_route` 通过 `Send` 并行分发四个角色，`merge_reviews` 去重合并；`finalize_node` 计算指纹并落 AgentRun。

### rag/
`KnowledgeBase` 从 JSON 加载 docs+terms；`KeywordBackend` 做 CJK token 重叠 + 术语别名扩展；`VectorBackend` 惰性导入 sentence-transformers。统一返回带引用的 chunks。

### review/dedup.py
`issue_dedup_key = category + 规范化标题`，跨角色合并证据与角色列表，再分配稳定编号并按严重度排序。

### prototype.py
按 PRDPage 列表生成单 HTML：导航、多状态区块（empty/error/loading）、表单校验 JS、深浅色切换；所有文本 `html.escape` 防注入。

### tasks.py
按 PRD 生成 database/backend/frontend/test 四类任务，带依赖关系与工作量等级，导出 Markdown/CSV/JSON。

## 5. 关键状态变化

一次运行 = 一个 AgentRun：running → succeeded/failed/needs_confirmation（human_confirm 时 interrupt_before split_tasks）。每步 append StepTrace；citations、fallbacks、errors 全量记录；最终 fingerprint 对 parsed+prd+issues+tasks 做 sha256，保证输出可复现。

## 6. 测试、评测、CI

- 39 个测试、90% 行覆盖率：schema、解析、审查规则、去重、PRD、原型转义、RAG 引用、任务拆分、端到端、API、CLI、fallback。
- `reqpilot eval`：12 条 golden 样例，输出成功率/完整性/召回/精确率/去重率，JSON+MD 落盘。
- CI：`.github/workflows/ci.yml`（uv + Python 3.12 + pytest + smoke + eval）。

## 7. 我的改动文件

全部为本人实现：`src/reqpilot/`（11 个模块）、`eval/cases/`（12 条标注样例）、`eval/knowledge/`（领域知识库）、`tests/`、CI、README、docs/design.md。

## 8. 失败 case 与 debug 过程

1. **LangGraph 1.x Send 报错**：节点直接返回 `list[Send]` 抛 `InvalidUpdateError: Expected dict`。定位：读 langgraph state.py 源码，确认 Send 必须由 `add_conditional_edges` 路由返回；改为 `review_route` 后并行生效。
2. **mock 解析器分类串味**：背景句（"目前…依赖线下"）把同句功能内容吞掉、字段句被逗号切碎导致字段丢失。修复：先抽字段再做子句分类、字段句从扫描文本剔除、目标用户/故事句不进功能需求。
3. **Python 3.14 wheel 兼容风险**：系统默认 3.14 太新，用 uv 固定 3.12 建独立 venv，规避原生扩展构建问题。
4. **Tailwind CDN 依赖网络**：原型默认引 CDN；测试与离线演示用 `offline=True` 生成无外链版本，README 标注。
