# ReqPilot 投递检查表

## 投递前必做

- [ ] GitHub 仓库已公开：https://github.com/Sh1njuuovo/reqpilot（README、LICENSE、CI badge、架构图齐全）
- [ ] 快速开始可复现：`export DEEPSEEK_API_KEY=... && uv sync --extra dev && uv run reqpilot smoke && uv run pytest`
- [ ] reports/eval 最新数字已核对（`uv run reqpilot eval` 重跑确认与简历一致）
- [ ] reports/demo 产物完整：prototype.html 可打开，prd.md、issues.json、tasks.md 与简历话术对应
- [ ] Agent 循环可演示：`uv run reqpilot demo && uv run reqpilot agent --workspace reports/demo`，能指着 summary.json 讲清 completion_claimed 与 completion_verified 的区别
- [ ] 脱敏检查：全库无公司名、团队人名与内部专有业务词（对内部版本里出现的专有名词逐一 grep 确认无命中）
- [ ] 简历版本已按目标 JD 选型：Agent 平台 → 版本一；后端 infra → 版本二；算法评测 → 版本三
- [ ] 简历每条 bullet 都能对应到代码行或运行结果（不写没跑过的指标）
- [ ] 简历与口播稿统一用"个人独立项目"口径，不出现公司、团队、业务方、线上用户

## 面试前

- [ ] 30 分钟 demo 脚本过一遍（reports/interview-pack/demo_script.md），重点是 Agent 循环那 6 分钟
- [ ] 31 条 Q&A 至少自问自答 2 遍，重点：LangGraph Send 报错、LLM 失败重试与收敛护栏、评测口径（精确率为什么低）、完成判定为什么不采信模型、沙箱如何阻止越界、提示词变体怎么选优、真实跑循环时踩过的三个坑
- [ ] 能徒手画两张图：管线节点链加四角色并行、Agent 循环的四步加程序侧校验
- [ ] 准备 5 个失败案例（Send 报错、批量限流、压缩吃掉目标、工具参数被输出截断、完成判定被模型声明绑架）和 2 个下一步计划
- [ ] 能对着代码讲三处具体实现：`WorkspaceSandbox.resolve`、`ContextManager.maybe_compress`、`AgentLoop.run` 里的 claim 分支

## 拿到 JD 后

- [ ] 用 JD 关键词调整简历 bullet 顺序与措辞（参考 job-search 里的 jd-tailoring 模板）
- [ ] 若 JD 强调 MCP：准备 mcp_server 的两个工具 demo 与"生产白名单加人工确认"设计
- [ ] 若 JD 强调评测：准备好评测方法论（人工评审 golden、召回与完整性为主指标、过度标注治理）
- [ ] 若 JD 强调提示词或效果调优：准备 `reqpilot tune` 的选优规则，并说清"先过滤超预算变体"这一步的理由
- [ ] 若 JD 强调 Agent 基础设施：把沙箱、工具集取舍、步数预算、上下文压缩这四点提到最前面讲
- [ ] 若 JD 强调后端：讲 FastAPI 五个端点、AgentRun 追踪与指纹、失败路径的 typed error
