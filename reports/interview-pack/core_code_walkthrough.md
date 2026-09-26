# ReqPilot 核心代码讲解稿

## 1. 入口

- CLI：`src/reqpilot/cli.py`，smoke / demo / agent / serve / eval / tune 六个子命令，默认 LLM provider。
- API：`src/reqpilot/api.py`，`POST /requirements` 触发一次完整管线，其余 GET 端点取 PRD/问题/任务/原型。
- MCP：`src/reqpilot/mcp_server.py`，stdio 暴露 `analyze_requirement`、`export_tasks`。
- 测试入口：`tests/test_pipeline.py` 端到端，`tests/test_agent_loop.py` 是 Agent 循环的行为测试，都用确定性替身，不打网络。

## 2. 配置

`src/reqpilot/config.py` 的 `Settings.from_env()`：`DEEPSEEK_API_KEY`/`OPENAI_API_KEY`、`REQPILOT_LLM_BASE_URL`、`REQPILOT_LLM_MODEL`、`REQPILOT_KNOWLEDGE_DIR`、`REQPILOT_MAX_ISSUES_PER_ROLE`。无 key 时 CLI/API 明确报错，不产出假内容。

## 3. 核心输入输出

- 输入：`RequirementInput{text, domain, source}`。
- 中间：`ParsedRequirement`（10 组字段）、`RetrievedChunk`（content/doc_id/section/score）。
- 输出：`ReviewIssue{role,category,severity,evidence,suggestion}`、`PRDDocument`、`DevelopmentTask`、`AgentRun{steps,citations,fingerprint,goal,tool_calls}`。

## 4. 管线模块

### providers/llm.py
OpenAI-compatible 调用。三个 JSON 任务（parse/review/generate_prd）用 response_format 强制 JSON，校验失败给一次修复机会，429/5xx/超时退避重试三次，提示词要求合并同类、每角色最多五条。同一文件还实现了 `plan_step`，用原生 tools 参数完成 Agent 循环的一步决策。

### pipeline.py（重点）
`PipelineBuilder` 用 LangGraph 组装节点。`_run_step` 统一计时、trace、异常捕获；`review_route` 通过 Send 并行分发四个角色；`merge_reviews` 做去重加每角色 Top-5 收敛；`finalize_node` 计算指纹并落 AgentRun；失败只记 typed error，不做内容兜底。

### rag/
`KnowledgeBase` 从 JSON 加载 docs 与 terms，`KeywordBackend`（中文分词加术语别名扩展）与可选 `VectorBackend` 统一返回带引用的 chunk。

### review/dedup.py
`issue_dedup_key` 由类别加规范化标题组成，跨角色合并证据与角色列表；`prune_issues` 按严重度每角色保留 Top-N，再统一编号。

### prompt_variants.py / tuning.py
评审提示词按变体命名存放，运行期用 `REQPILOT_PROMPT_VARIANT` 切换。`tuning.py` 逐变体跑一遍评测，按"先过滤问题数超预算、再取召回最高、并列取列表最短"的规则选优，报告写进 reports/tuning。

### prototype.py / tasks.py
单 HTML 多页面原型生成，带多状态、表单校验、深浅色和 html.escape 防注入；PRD 到四类任务拆分，带依赖关系与 Markdown/CSV/JSON 导出。

## 5. Agent 循环模块（重点）

目录是 `src/reqpilot/agent/`，四个文件各管一件事。

### sandbox.py
`WorkspaceSandbox` 是所有文件访问的唯一入口。`resolve()` 把相对路径和绝对路径都解析成真实路径，再判断是否在工作区内，越界抛 `SandboxViolation`。`run_command()` 先用 shlex 拆参数，要求第一个参数在只读白名单里，`find -exec` 和 `sort -o` 列为禁用参数，任何带斜杠的参数都要过一遍归属检查，最后用 subprocess 执行且 `shell=False`，所以管道和重定向不是绕过的路径。

### tools.py
`ToolRegistry` 持有工具声明与处理函数，`openai_tools()` 把声明渲染成模型能用的格式，`call()` 把沙箱异常转成结构化的失败结果。工具集只有 ls、read、write、edit、grep、find、bash，循环另外注册一个 remember。

### context.py
`estimate_tokens` 做中英混排的粗略估算，`ContextManager` 维护消息列表，超过预算九成时把较早的消息折叠成一条摘要，折叠点会回退到不切断"助手消息加工具结果"的位置。完整消息追加到 session.jsonl，长期记忆写进 MEMORY.md。摘要函数出错时退到确定性摘要，不让压缩本身把循环弄挂。

### loop.py
`AgentLoop` 是循环本体。每轮先压缩上下文，再让 provider 给出一步决策，记录 StepTrace 与 ToolCallTrace，执行工具并把结果写回上下文。模型声明完成时调用校验函数，通过才把目标标成 completed；每轮结束后也会主动跑一次校验，通过但模型没声明就提示它调用 goal_complete。步数用尽标 step_limit，provider 抛错标 failed。最终指纹覆盖目标、状态和全部工具调用。

### checks.py
默认目标的验收函数。读 issues.json 拿到 critical 与 major 的问题编号，要求 review-fixes.md 逐条覆盖，同时要求 tasks.md 仍然存在。校验只读文件，不看模型的话。

## 6. 关键状态变化

管线一次运行对应一个 AgentRun，状态从 running 走到 succeeded、failed 或 needs_confirmation（human_confirm 时在 split_tasks 前中断）。Agent 循环同样写 AgentRun，额外带上 goal 与 tool_calls。两者的指纹都是 sha256，前者覆盖 parsed、prd、issues、tasks，后者覆盖目标、状态和工具调用序列。

## 7. 测试、评测、CI

- 125 个测试、93% 行覆盖率。覆盖 schema、提示词结果校验、去重收敛、原型转义、RAG 引用、任务拆分、端到端、API、CLI、重试与失败路径、提示词变体选优规则，以及 Agent 循环的沙箱越界、只读命令白名单、上下文压缩、验收失败回灌、步数上限、输出截断、工具失败继续跑。
- `reqpilot eval`：12 条人工评审标准样例，DeepSeek 实测成功率 12/12、问题召回 93.8%、平均 14.1s，JSON 与 Markdown 落盘并附逐条问题明细。
- CI：pytest 常跑；LLM smoke 与 eval 在配置 key 时运行。

## 8. 我的改动文件

全部为本人实现：`src/reqpilot/`（含 `src/reqpilot/agent/`、`prompt_variants.py`、`tuning.py`）、`eval/cases/`（12 条标注样例）、`eval/knowledge/`、`tests/`、CI、README、`docs/design.md`、`docs/project-story.md`。

## 9. 失败 case 与 debug 过程

1. **LangGraph 1.x Send 报错**：节点直接返回 `list[Send]` 抛 `InvalidUpdateError`，读 langgraph 源码确认 Send 必须由 `add_conditional_edges` 路由返回，修复后并行生效。
2. **LLM 批量评测偶发失败**：连续请求时出现限流与超时导致 4/12 失败，加入 429/5xx 指数退避重试后恢复到 100% 成功率。
3. **LLM 过度标注**：模型单条产出 20 多个问题，标签精确率被稀释，加入"宁缺毋滥"提示词、去重和每角色 Top-5 收敛护栏，把列表压到可审阅规模。
4. **Agent 循环验收阈值过紧**：验收函数一开始要求文件内容至少 20 字符，导致只有一行标题的 tasks.md 被判失败，改成 10 字符常量并补了边界测试。
5. **压缩把目标吃掉**：第一次用真模型跑循环时，八步全在读取。查 transcript 发现目标写在普通消息里，连续压缩后目标被折进嵌套摘要，模型手里没有目标了。改成目标进系统提示，并给上下文加钉住条数，前两条永不参与压缩。
6. **工具参数被输出截断**：模型把 4000 多字的整改文件塞进一次 write，撞上 max_tokens 上限导致参数 JSON 不闭合，报错信息还是"path 必须是非空字符串"，模型连按同样方式试了四次。改成上调并暴露单步输出上限、识别 finish_reason 为 length 并说明本次调用未执行、增加 append 支持分批写入，同时在参数解析保留原始串便于排查。
7. **完成判定被模型声明绑架**：有一次验收四项全过，但模型没在预算内调用 goal_complete，被判 step_limit 失败。改成步数用尽时也跑验收，通过即按完成记录，并在 checks 与 fallbacks 里写明模型未主动声明。
8. **Python 3.14 wheel 兼容风险**：用 uv 固定 3.12 建独立 venv，规避原生扩展构建问题。
