# ReqPilot 核心代码讲解稿

## 1. 入口

- CLI：`src/reqpilot/cli.py`，smoke/demo/serve/eval 四个子命令，默认 LLM provider。
- API：`src/reqpilot/api.py`，`POST /requirements` 触发一次完整管线，其余 GET 端点取 PRD/问题/任务/原型。
- MCP：`src/reqpilot/mcp_server.py`，stdio 暴露 `analyze_requirement`、`export_tasks`。
- 测试入口：`tests/test_pipeline.py` 端到端（用确定性替身，不打网络）。

## 2. 配置

`src/reqpilot/config.py` 的 `Settings.from_env()`：`DEEPSEEK_API_KEY`/`OPENAI_API_KEY`、`REQPILOT_LLM_BASE_URL`、`REQPILOT_LLM_MODEL`、`REQPILOT_KNOWLEDGE_DIR`、`REQPILOT_MAX_ISSUES_PER_ROLE`。无 key 时 CLI/API 明确报错，不产出假内容。

## 3. 核心输入输出

- 输入：`RequirementInput{text, domain, source}`。
- 中间：`ParsedRequirement`（10 组字段）、`RetrievedChunk`（content/doc_id/section/score）。
- 输出：`ReviewIssue{role,category,severity,evidence,suggestion}`、`PRDDocument`、`DevelopmentTask`、`AgentRun{steps,citations,fingerprint}`。

## 4. 核心模块

### providers/llm.py
OpenAI-compatible 调用：三个 JSON 任务（parse/review/generate_prd），response_format 强制 JSON；校验失败给一次修复机会；429/5xx/超时指数退避重试 3 次；prompt 要求"合并同类、每角色最多 5 条、宁缺毋滥"。

### pipeline.py（重点）
`PipelineBuilder` 用 LangGraph 组装节点；`_run_step` 统一计时、trace、异常捕获；`review_route` 通过 `Send` 并行分发四个角色；`merge_reviews` 做去重 + 每角色 Top-5 收敛；`finalize_node` 计算指纹并落 AgentRun；失败只记 typed error，不做内容兜底。

### rag/
`KnowledgeBase` 从 JSON 加载 docs+terms；`KeywordBackend`（CJK token + 术语别名扩展）与可选 `VectorBackend`（sentence-transformers）统一返回带引用的 chunks。

### review/dedup.py
`issue_dedup_key = category + 规范化标题`，跨角色合并证据与角色列表；`prune_issues` 按严重度每角色保留 Top-N，再统一编号。

### prototype.py / tasks.py
单 HTML 多页面原型生成（多状态、表单校验、深浅色、html.escape 防注入）；PRD 到四类任务拆分（database/backend/frontend/test）带依赖与导出。

## 5. 关键状态变化

一次运行 = 一个 AgentRun：running → succeeded/failed/needs_confirmation（human_confirm 时 interrupt_before split_tasks）。每步 append StepTrace；citations、errors 全量记录；最终 fingerprint 对 parsed+prd+issues+tasks 做 sha256。

## 6. 测试、评测、CI

- 42 个测试、90% 行覆盖率：schema、提示词结果校验、去重收敛、原型转义、RAG 引用、任务拆分、端到端、API、CLI、重试/失败路径。
- `reqpilot eval`：12 条人工评审标准样例，DeepSeek 实测成功率 100%、完整性 100%、召回 86.5%，JSON+MD 落盘并附逐条问题明细。
- CI：pytest 常跑；LLM smoke/eval 在配置 key 时运行（env guard）。

## 7. 我的改动文件

全部为本人实现：`src/reqpilot/`、`eval/cases/`（12 条标注样例）、`eval/knowledge/`、`tests/`、CI、README、docs/design.md。

## 8. 失败 case 与 debug 过程

1. **LangGraph 1.x Send 报错**：节点直接返回 `list[Send]` 抛 `InvalidUpdateError`，读 langgraph 源码确认 Send 必须由 `add_conditional_edges` 路由返回，修复后并行生效。
2. **LLM 批量评测偶发失败**：72 连发时出现限流/超时导致 4/12 失败，加入 429/5xx 指数退避重试后恢复 100% 成功率。
3. **LLM 过度标注**：模型单条产出 20+ 问题、标签精确率被稀释，加入"宁缺毋滥"提示词 + 去重 + 每角色 Top-5 收敛护栏，把列表控制到可审阅规模。
4. **Python 3.14 wheel 兼容风险**：用 uv 固定 3.12 建独立 venv，规避原生扩展构建问题。
