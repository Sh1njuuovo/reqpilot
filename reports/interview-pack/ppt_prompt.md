# ReqPilot PPT 生成提示词

请生成一份 12-14 页中文项目介绍 PPT，目标岗位为大厂 Agent 相关 HC（LLM 应用 / Agent 平台方向），按以下结构：

1. 封面：ReqPilot——LLM 驱动的需求工程 Agent；副标题"从需求文本到 PRD、审查、原型与任务，以及一个会自己收尾的沙箱循环"；作者：独立设计与实现。
2. 问题背景：需求写成一段话就开工，权限、异常路径、验收标准缺失，返工成本落在实现者身上。用一张对照图展示"一句话需求"与"补齐后的需求"，注意不要用公司或业务方叙事，讲课程与个人项目场景。
3. 方案总览：输入（自然语言需求）→ 固定管线（解析／RAG／四角色并行审查／去重收敛／PRD／原型／任务）→ Agent 循环（沙箱内整改）→ 输出与证据。
4. 系统架构图：LangGraph 节点链标出 parse、retrieve、fan_out_review、review_one、merge_reviews、build_prd、build_prototype、split_tasks、finalize，同时标出 LLM provider 与可插拔 RAG。
5. 多角色审查：四个 LLM Agent 的职责矩阵（产品／前端／后端／测试 × 检查项），问题池去重与每角色 Top-5 收敛的流程图。
6. Agent 循环（核心页）：画出观察、决策、执行、写回上下文、判断收尾的循环，标注四个关键设计——工作区沙箱、只读命令白名单、token 预算与记忆落盘、目标完成由程序校验。
7. 可靠性与安全：Pydantic 结构化输出加一次修复、退避重试三次、typed error、失败标 failed 不产出伪结果；沙箱的路径约束与禁用参数清单。
8. 评测：表格展示 12 条人工评审标准样例实测（成功率 12/12、问题召回 93.8%、平均 14.1s/条），并单独一栏说明精确率约 22.7% 的原因是模型过度标注，收敛护栏为此设计。注明口径与复现命令。
9. 工程质量：125 个测试、93% 行覆盖率、GitHub Actions CI；FastAPI、CLI 六命令、MCP stdio server；Agent 循环用确定性替身离线测试。
10. 提示词变体选优：同一套样例下三个提示词变体的实测对比（baseline 召回 90.0% 胜出，coverage_first 精确率 26.7% 但成功率 75%），说明选优规则，报告落在 reports/tuning。
11. Demo 截图：放 reports/demo/prototype.html 的截图与 reports/agent/summary.json 的字段对照（completion_claimed 与 completion_verified），配 2-3 句讲解。
12. 限制与下一步：领域泛化依赖知识库质量、评测规模小、版本差异未做；下一步扩样例集、加 LLM-as-judge 有效性抽样、把沙箱换成容器。

风格：技术简洁风，深蓝主色；每页不超过 5 个要点；图表优先于文字；不要出现任何虚构的团队、公司或线上用户数据。
