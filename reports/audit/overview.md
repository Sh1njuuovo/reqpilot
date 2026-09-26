# reqpilot 项目摸底报告

## 基本信息

| 字段 | 值 |
| --- | --- |
| repo_path | /Users/shinjuu/intern/ReqPilot |
| generated_at | 2026-09-26T08:26:36.359810+00:00 |
| file_count_scanned | 111 |
| approx_total_bytes | 1309712 |

## 语言和文件类型

| 语言 | 文件数 |
| --- | --- |
| Other | 60 |
| Python | 49 |
| TOML | 1 |
| YAML | 1 |

## 依赖和环境线索

- `pyproject.toml`

## README

- `README.md`

## 核心链路线索

| 类别 | 命中文件数 | 代表路径 |
| --- | --- | --- |
| api_backend | 5 | eval/knowledge/domain.json<br>src/reqpilot/__main__.py<br>src/reqpilot/api.py<br>src/reqpilot/mcp_server.py<br>tests/test_api.py |
| async_jobs | 8 | reports/demo/tasks.csv<br>reports/demo/tasks.json<br>reports/demo/tasks.md<br>reports/smoke/tasks.csv<br>reports/smoke/tasks.json<br>reports/smoke/tasks.md<br>src/reqpilot/tasks.py<br>tests/test_tasks.py |
| config | 1 | src/reqpilot/config.py |
| database_state | 4 | src/reqpilot/agent/sandbox.py<br>src/reqpilot/models.py<br>tests/test_agent_sandbox.py<br>tests/test_models.py |
| devops_deploy | 5 | .github/workflows/ci.yml<br>reports/demo/citations.json<br>reports/smoke/citations.json<br>src/reqpilot/pipeline.py<br>tests/test_pipeline.py |
| evaluation | 37 | eval/cases/case_001.json<br>eval/cases/case_002.json<br>eval/cases/case_003.json<br>eval/cases/case_004.json<br>eval/cases/case_005.json<br>eval/cases/case_006.json<br>eval/cases/case_007.json<br>eval/cases/case_008.json |
| frontend_mobile | 15 | .DS_Store<br>reports/.DS_Store<br>reports/audit/overview.html<br>reports/audit/overview.md<br>reports/interview-pack/application_checklist.md<br>reports/interview-pack/core_code_walkthrough.md<br>reports/interview-pack/demo_script.md<br>reports/interview-pack/interview_qa.md |
| inference_demo | 16 | reports/demo/citations.json<br>reports/demo/issues.json<br>reports/demo/parsed.json<br>reports/demo/prd.json<br>reports/demo/prd.md<br>reports/demo/prototype.html<br>reports/demo/run.json<br>reports/demo/summary.json |
| model | 2 | src/reqpilot/models.py<br>tests/test_models.py |
| security_auth | 3 | reports/audit/audit.json<br>reports/audit/overview.html<br>reports/audit/overview.md |
| testing_quality | 22 | .coverage<br>reports/eval/eval_llm_keyword_latest.json<br>reports/eval/eval_llm_keyword_latest.md<br>src/reqpilot/providers/mock.py<br>tests/test_agent_checks.py<br>tests/test_agent_context.py<br>tests/test_agent_loop.py<br>tests/test_agent_sandbox.py |

## Notebook / Docker / Test 线索

### Notebooks
- 无

### Docker
- 无

### Tests
- `reports/eval/eval_llm_keyword_latest.json`
- `reports/eval/eval_llm_keyword_latest.md`
- `tests/test_agent_checks.py`
- `tests/test_agent_context.py`
- `tests/test_agent_loop.py`
- `tests/test_agent_sandbox.py`
- `tests/test_agent_tools.py`
- `tests/test_api.py`
- `tests/test_cli.py`
- `tests/test_dedup.py`
- `tests/test_llm_agent_step.py`
- `tests/test_mcp.py`
- `tests/test_mock_parse.py`
- `tests/test_models.py`
- `tests/test_pipeline.py`
- `tests/test_prd.py`
- `tests/test_prototype.py`
- `tests/test_rag.py`
- `tests/test_review_rules.py`
- `tests/test_tasks.py`

## 潜在数据/状态/模型/资源路径

- 无

## 目录树摘要

```text
ReqPilot/
  .github/
  docs/
  eval/
  reports/
  src/
  tests/
  .DS_Store
  .coverage
  .gitignore
  .python-version
  LICENSE
  README.md
  pyproject.toml
  uv.lock
    workflows/
      ci.yml
    design.md
    project-story.md
    cases/
    knowledge/
      case_001.json
      case_002.json
      case_003.json
      case_004.json
      case_005.json
      case_006.json
      case_007.json
      case_008.json
      case_009.json
      case_010.json
      case_011.json
      case_012.json
      domain.json
    audit/
    demo/
    eval/
    interview-pack/
    smoke/
    .DS_Store
      audit.json
      overview.html
      overview.md
      citations.json
      issues.json
      parsed.json
      prd.json
      prd.md
      prototype.html
      run.json
      summary.json
      tasks.csv
      tasks.json
      tasks.md
      eval_llm_keyword_20260826_124248.json
      eval_llm_keyword_20260826_124248.md
      eval_llm_keyword_latest.json
      eval_llm_keyword_latest.md
      application_checklist.md
      core_code_walkthrough.md
      demo_script.md
      interview_qa.md
      ppt_prompt.md
      resume_star.md
      citations.json
      issues.json
      parsed.json
      prd.json
      prd.md
      prototype.html
      run.json
      summary.json
      tasks.csv
      tasks.json
      tasks.md
    reqpilot/
    .DS_Store
      agent/
      eval/
      providers/
      rag/
      review/
      .DS_Store
      __init__.py
      __main__.py
      api.py
      cli.py
      config.py
      mcp_server.py
      models.py
      pipeline.py
      prd.py
      prototype.py
      tasks.py
    test_agent_checks.py
    test_agent_context.py
    test_agent_loop.py
    test_agent_sandbox.py
    test_agent_tools.py
    test_api.py
    test_cli.py
    test_dedup.py
    test_llm_agent_step.py
    test_mcp.py
    test_mock_parse.py
    test_models.py
    test_pipeline.py
    test_prd.py
    test_prototype.py
    test_rag.py
    test_review_rules.py
    test_tasks.py
```

## 下一步人工确认

- 找到最小可运行命令：API、页面、CLI、worker、测试、训练或 demo 至少一个。
- 确认依赖、环境变量、数据库/数据文件、端口和外部服务。
- 确认 baseline/demo 是否能在本地、Docker、云服务器或 GPU 环境上跑通。
- 确认自己要做的面试亮点：改造点、demo、测试、报告或实验计划。
