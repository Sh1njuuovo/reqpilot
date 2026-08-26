# ReqPilot 投递检查表

## 投递前必做

- [ ] GitHub 仓库已公开：https://github.com/Sh1njuuovo/reqpilot（README、LICENSE、CI badge、架构图齐全）
- [ ] README 快速开始可复现：`uv sync --extra dev && uv run reqpilot smoke && uv run pytest`
- [ ] reports/eval 最新数字已核对（`uv run reqpilot eval` 重跑确认与简历一致）
- [ ] reports/demo 产物完整：prototype.html 可打开、prd.md/issues.json/tasks.md 内容与简历话术对应
- [ ] 脱敏检查：全库无公司名、团队人名与内部专有业务词（对内部版本里出现的专有名词逐一 grep 确认无命中）
- [ ] 简历版本已按目标 JD 选型：Agent 平台 → 版本一；后端 infra → 版本二；算法评测 → 版本三
- [ ] 简历每条 bullet 都能对应到代码行或运行结果（不写没跑过的指标）

## 面试前

- [ ] 30 分钟 demo 脚本过一遍（reports/interview-pack/demo_script.md）
- [ ] 18 条 Q&A 至少自问自答 2 遍，重点：LangGraph Send 报错、mock/LLM 双 provider、评测口径
- [ ] 能徒手画架构图：LangGraph 节点链 + 四角色并行 + RAG 引用
- [ ] 准备 2 个失败案例（Send 报错、解析分类串味）和 2 个下一步计划

## 拿到 JD 后

- [ ] 用 JD 关键词调整简历 bullet 顺序与措辞（参考 job-search 里的 jd-tailoring 模板）
- [ ] 若 JD 强调 MCP：准备 mcp_server 的两个工具 demo 与"生产白名单+人工确认"设计
- [ ] 若 JD 强调评测：准备好双 provider 对照实验设计（LLM 跑 12 条样例的预期差异）
