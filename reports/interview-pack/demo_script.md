# ReqPilot 30 分钟 Demo 脚本

前置：`export DEEPSEEK_API_KEY=... && uv sync --extra dev && uv run reqpilot demo`，产物在 `reports/demo/`。

## 0-3 分钟：定位与一句话

"这是一个 LLM 驱动的需求工程 Agent。自然语言需求进去，结构化 PRD、四角色审查报告、可点击原型、研发任务出来。模型负责理解和生成，校验、收敛和执行边界由工程层保证。除了固定管线，还有一个沙箱里的目标循环，能自己选工具把评审问题处理掉。"

## 3-8 分钟：跑一遍全链路（reports/demo/summary.json）

执行 `uv run reqpilot smoke`，指着 summary 讲：解析出的功能需求、数据字段、审查问题条数与去重前后的差值、PRD 页面数、任务数，以及 DeepSeek 下的耗时。强调每个环节都是真实 LLM 输出加 Pydantic 校验，没有 key 时命令会直接报错而不是给假内容。

## 8-15 分钟：多角色审查（reports/demo/issues.json）

挑三条问题讲，后端那条讲幂等，前端那条讲重复提交，产品那条讲审批流配置缺规则说明。说明四角色各自的职责边界，每条都带 evidence 依据。再讲收敛护栏，跨角色同质问题合并，每角色按严重度保留 Top-5，保证列表可人审。

## 15-21 分钟：PRD 与原型（reports/demo/prd.md、prototype.html）

打开 prototype.html，讲单 HTML 多页面、空状态与错误状态、表单必填校验、深浅色切换。回到 prd.md 讲结构化数据到模板渲染的做法，页面与功能需求一一对应。

## 21-27 分钟：Agent 循环（重点，`uv run reqpilot agent --workspace reports/demo`）

这段是全场最该讲的部分。先讲目标：issues.json 里 critical 和 major 的问题，每一条都要在 review-fixes.md 里给出结论，同时 tasks.md 不能丢。

然后按四句讲清楚它为什么是 Agent 而不是脚本：

1. 模型自己选工具。工作区里有什么、下一步读哪个文件、要不要先 grep，都由模型决定，代码里没有写死的步骤顺序。
2. 工具执行有边界。所有路径过同一个沙箱入口，越界直接报错；bash 只允许只读白名单且不经 shell 执行，`find -exec`、`sort -o` 这类参数被单独禁用。
3. 上下文自己管。消息超过 token 预算就把旧消息压成摘要，完整记录写 session.jsonl，跨运行结论写 MEMORY.md，下一轮会重新注入。
4. 完成由程序判定。模型调用 goal_complete 只是触发校验，验收函数直接读工作区文件，不满足就把原因回灌让它继续跑，跑满步数预算判定失败。

展示 `reports/agent/summary.json` 里的 status、steps_used、tool_counts、completion_claimed 与 completion_verified 两个字段的区别，这两个字段就是"模型说完成"和"程序确认完成"的分界。

## 27-30 分钟：评测口径与收尾

打开 reports/eval/eval_llm_keyword_latest.md，讲 12 条人工评审标准样例的口径：成功率、字段完整性、问题召回、去重率。主动讲精确率只有 22.7% 是模型过度标注，收敛护栏就是为它设计的。再讲提示词不是靠手调：`uv run reqpilot tune` 会把命名变体在同一套样例上比一遍，先过滤问题数超预算的变体，再取召回最高的，实测 baseline 召回 90.0% 胜出，coverage_first 精确率更高但成功率掉到 75%。收尾讲失败 case（Send 报错、批量限流、压缩吃掉目标、工具参数被截断）和生产路径（pgvector、MCP 写回、Playwright 验证、沙箱换容器）。
