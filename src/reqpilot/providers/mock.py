"""Deterministic rule-based provider.

Runs the full pipeline without any API key and produces stable, explainable
output that unit tests and the evaluation suite can assert against.
"""

from __future__ import annotations

import re

from reqpilot.models import (
    DataEntity,
    DataField,
    FormField,
    FunctionalRequirement,
    ParsedRequirement,
    PRDDocument,
    PRDPage,
    ReviewIssue,
)

ACTION_VERBS = (
    "支持|需要|可以|实现|提供|允许|能够|展示|查询|新增|编辑|修改|删除|提交|审批|导出|导入|"
    "生成|同步|统计|搜索|筛选|下载|上传|查看|录入"
)
CONSTRAINT_WORDS = "必须|只能|不允许|不能|不得|禁止|限制|不超过|仅限|超过|最多|最少"
BACKGROUND_WORDS = "背景|现状|目前|当前|由于|随着|现有|流程长|链条长|效率低|周期长|依赖"
PERMISSION_ACTION = (
    "只能|可编辑|只读|可查看|可审批|可审核|可配置|可操作|可访问|可导出|可导入|可提交|"
    "查看全部|全部数据|全部记录|全部单据|全部申请|按角色"
)


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"[。！？；\n]+", text) if s.strip()]


def _guess_field_type(name: str) -> str:
    if any(k in name for k in ("金额", "数量", "费用", "价格", "积分")):
        return "number"
    if any(k in name for k in ("日期", "时间")):
        return "date"
    if any(k in name for k in ("状态", "类型", "类别")):
        return "enum"
    return "string"


class MockProvider:
    """Rule-based provider with deterministic extraction, review, and PRD generation."""

    name = "mock"

    def parse(self, text: str, domain: str) -> ParsedRequirement:
        sents = _sentences(text)
        parsed = ParsedRequirement()
        clauses = [c.strip() for c in re.split(r"[。！？；\n，,、]+", text) if c.strip()]

        # user stories (sentence-level; the pattern spans a comma)
        stories: list[str] = []
        for s in sents:
            m = re.search(
                r"(?:作为|我是)([^，。]{2,20})[，,](?:我)?(?:想要|需要|希望能|要|可以)([^。]{2,80})",
                s,
            )
            if m:
                stories.append(f"作为{m.group(1).strip()}，我想要{m.group(2).strip()}")
        parsed.user_stories = list(dict.fromkeys(stories))

        # target users (whole-text regex)
        users: list[str] = []
        for m in re.finditer(
            r"面向([^，。]{2,20})|给([^，。]{2,20})(?:使用|体验|用)|(?:用户|使用者)(?:包括|是|为)([^，。]{2,20})",
            text,
        ):
            users.append(next((g for g in m.groups() if g), "").strip())
        parsed.target_users = list(dict.fromkeys(u for u in users if u))

        # data fields first, so classifier can skip pure field-name clauses
        fields: dict[str, DataField] = {}
        for clause in clauses:
            m = re.search(r"(?:字段|数据项)(?:包括|有|为|包含|：|:|\s)*([^。]+)", clause)
            if not m:
                continue
            for part in re.split(r"[、，,]", m.group(1)):
                part = re.sub(r"^(?:必填项?为|必填|为|包含|有)", "", part).strip()
                if part and part not in fields:
                    fields[part] = DataField(name=part, type=_guess_field_type(part))
        scan_clauses = [c for c in clauses if not re.search(r"字段|数据项", c)]
        scan_text = "".join(scan_clauses)
        for m in re.finditer(
            r"([\u4e00-\u9fa5A-Za-z0-9]{2,12})(名称|编号|金额|日期|类型|状态|数量|账号|密码|备注|邮箱|电话)",
            scan_text,
        ):
            name = re.sub(r"^(?:必填项?为|必填|为|包含|包括|有)", "", m.group(0))
            if name not in fields:
                fields[name] = DataField(name=name, type=_guess_field_type(name))
        for m in re.finditer(r"(?:^|[，,、\s])(金额|数量|账号|邮箱|电话)(?=[，,、。\s]|$)", text):
            name = m.group(1)
            if name not in fields:
                fields[name] = DataField(name=name, type=_guess_field_type(name))
        parsed.data_fields = list(fields.values())

        # clause-level classification with priority:
        # background > permission > constraint > exception > acceptance > field > functional
        background: list[str] = []
        perms: list[str] = []
        constraints: list[str] = []
        exceptions: list[str] = []
        acceptance: list[str] = []
        funcs: list[str] = []
        for clause in clauses:
            if re.search(BACKGROUND_WORDS, clause):
                background.append(clause)
                continue
            if re.search(r"权限|角色|管理员|审批人|只读|可编辑", clause) and re.search(
                PERMISSION_ACTION, clause
            ):
                perms.append(clause)
                continue
            if re.search(CONSTRAINT_WORDS, clause):
                constraints.append(clause)
                continue
            if re.search(r"异常|失败|超时|错误|重试|回滚|兜底|中断", clause):
                exceptions.append(clause)
                continue
            if re.search(r"验收|通过标准|预期|达成|上线标准", clause):
                acceptance.append(clause)
                continue
            if re.search(r"字段|数据项", clause):
                continue
            if clause in fields:
                continue
            if re.search(ACTION_VERBS, clause) and not re.search(r"面向|作为|我是", clause):
                funcs.append(clause)
        parsed.background = "；".join(background[:2]) if background else None
        parsed.permissions = list(dict.fromkeys(perms))
        parsed.constraints = list(dict.fromkeys(constraints))
        parsed.exception_flows = list(dict.fromkeys(exceptions))
        parsed.acceptance_criteria = list(dict.fromkeys(acceptance))
        parsed.functional_requirements = funcs

        return parsed

    def review(self, role: str, parsed: ParsedRequirement, context: str) -> list[ReviewIssue]:
        issues: list[ReviewIssue] = []
        if role == "product":
            issues.extend(self._review_product(parsed))
        elif role == "frontend":
            issues.extend(self._review_frontend(parsed, context))
        elif role == "backend":
            issues.extend(self._review_backend(parsed, context))
        elif role == "test":
            issues.extend(self._review_test(parsed, context))
        return issues

    @staticmethod
    def _issue(role: str, category: str, severity: str, title: str, description: str, suggestion: str = "") -> ReviewIssue:
        return ReviewIssue(
            role=role,  # type: ignore[arg-type]
            category=category,  # type: ignore[arg-type]
            severity=severity,  # type: ignore[arg-type]
            title=title,
            description=description,
            suggestion=suggestion,
        )

    def _review_product(self, parsed: ParsedRequirement) -> list[ReviewIssue]:
        out: list[ReviewIssue] = []
        if not parsed.target_users:
            out.append(self._issue("product", "completeness", "major", "缺少目标用户定义",
                                   "未从需求中提取到目标用户，评审无法判断使用范围。", "补充目标用户及典型使用场景"))
        if not parsed.acceptance_criteria:
            out.append(self._issue("product", "completeness", "major", "缺少验收标准",
                                   "没有可验证的验收标准，需求完成度无法度量。", "补充验收标准与预期结果"))
        if not parsed.functional_requirements:
            out.append(self._issue("product", "completeness", "critical", "未识别到功能需求",
                                   "解析结果中没有功能需求条目。", "补充功能点描述"))
        if not parsed.background:
            out.append(self._issue("product", "completeness", "minor", "缺少需求背景说明",
                                   "缺少背景信息，无法判断需求的动机与优先级。", "补充需求背景"))
        if parsed.functional_requirements and not parsed.user_stories:
            out.append(self._issue("product", "completeness", "suggestion", "建议补充用户故事",
                                   "功能需求存在但没有用户故事视角。", "用'作为X，我想要Y'补充"))
        return out

    def _review_frontend(self, parsed: ParsedRequirement, context: str) -> list[ReviewIssue]:
        out: list[ReviewIssue] = []
        if not re.search(r"页面|界面|列表|表单|弹窗|展示|交互|流程", context):
            out.append(self._issue("frontend", "interaction", "minor", "缺少页面与交互描述",
                                   "需求文本中没有页面或交互相关的描述。", "补充页面结构与关键交互"))
        if re.search(r"表单|填写|输入|提交|录入", context) and not re.search(r"校验|必填|格式|长度|范围|最大|最小", context):
            out.append(self._issue("frontend", "interaction", "major", "表单缺少校验规则",
                                   "存在表单录入但未定义必填、格式或长度校验。", "定义必填项与格式校验"))
        if re.search(r"列表|查询|搜索|筛选", context) and not re.search(r"空|无数据|加载|失败|错误|异常", context):
            out.append(self._issue("frontend", "interaction", "minor", "列表缺少空态与异常态",
                                   "列表场景未描述空数据、加载失败等状态。", "补充空态/加载/失败态"))
        if re.search(r"权限|角色|管理员|审批人", context) and not re.search(r"不同角色|角色差异|按角色|只读|可编辑|隐藏", context):
            out.append(self._issue("frontend", "permission", "minor", "页面缺少按角色差异展示说明",
                                   "存在多角色但未说明各角色看到的页面差异。", "补充角色差异展示规则"))
        return out

    def _review_backend(self, parsed: ParsedRequirement, context: str) -> list[ReviewIssue]:
        out: list[ReviewIssue] = []
        if re.search(r"数据|记录|字段|保存|提交|存储", context) and not parsed.data_fields:
            out.append(self._issue("backend", "data", "major", "缺少数据字段定义",
                                   "需求涉及数据保存/展示但未定义数据字段。", "补充核心数据字段与类型"))
        if re.search(r"权限|角色|管理员|审批", context) and not parsed.permissions:
            out.append(self._issue("backend", "permission", "critical", "缺少权限模型定义",
                                   "需求涉及权限/角色但没有权限模型。", "定义角色、权限点与数据权限"))
        if re.search(r"提交|支付|转账|保存|发布|创建|删除|审批通过|审批拒绝", context) and not re.search(
            r"幂等|重复提交|防重|唯一", context
        ):
            out.append(self._issue("backend", "logic", "major", "写操作缺少幂等性设计",
                                   "存在写操作但未考虑重复提交。", "引入幂等键或防重校验"))
        if re.search(r"查询|列表|搜索", context) and not re.search(r"分页|翻页|limit|上限|最大", context):
            out.append(self._issue("backend", "logic", "minor", "列表接口缺少分页约定",
                                   "列表查询未定义分页与返回上限。", "补充分页参数与默认大小"))
        return out

    def _review_test(self, parsed: ParsedRequirement, context: str) -> list[ReviewIssue]:
        out: list[ReviewIssue] = []
        if re.search(r"提交|审批|导入|导出|删除|发布|转账", context) and not parsed.exception_flows:
            out.append(self._issue("test", "logic", "major", "缺少异常与边界用例",
                                   "关键操作未描述失败路径，测试无法覆盖异常。", "补充失败/重试/回滚场景"))
        if not parsed.acceptance_criteria:
            out.append(self._issue("test", "completeness", "major", "缺少验收标准",
                                   "缺少可量化验收标准，无法编写验收用例。", "将验收标准转为可断言用例"))
        if re.search(r"分页|批量|大量|超过|上限", context) and not re.search(r"上限|最大|最多|限制", context):
            out.append(self._issue("test", "logic", "minor", "缺少分页/批量边界用例",
                                   "存在分页或批量场景但未定义边界。", "补充边界值用例"))
        if parsed.data_fields and not re.search(r"必填|非空|长度|格式|范围", context):
            out.append(self._issue("test", "data", "minor", "缺少字段级校验用例",
                                   "有数据字段但未定义字段校验用例。", "补充必填/格式/长度用例"))
        return out

    def generate_prd(self, parsed: ParsedRequirement, domain: str, context: str) -> PRDDocument:
        funcs = [
            FunctionalRequirement(
                id=f"FR-{i + 1}",
                title=s[:24] + ("…" if len(s) > 24 else ""),
                description=s,
                priority="P0" if i == 0 else "P1",
            )
            for i, s in enumerate(parsed.functional_requirements)
        ]
        title = f"{funcs[0].title}需求说明书" if funcs else "需求规格说明书"

        pages: list[PRDPage] = []
        for i, fr in enumerate(funcs):
            comps: list[str] = []
            if re.search(r"表单|录入|新增|编辑|提交|审批", fr.description):
                comps.append("form")
            if re.search(r"列表|查询|搜索|展示|查看", fr.description):
                comps.append("table")
            if not comps:
                comps = ["card", "button"]
            states = ["default"]
            if "table" in comps:
                states += ["empty", "error"]
            if re.search(r"查询|加载", fr.description):
                states.append("loading")
            form_fields = [
                FormField(name=f.name, label=f.name, type="number" if f.type == "number" else ("date" if f.type == "date" else "text"), required=f.required)
                for f in parsed.data_fields[:6]
            ]
            interactions = ["表单校验", "提交成功/失败提示"]
            if "table" in comps:
                interactions.append("列表查询与分页")
            interactions = list(dict.fromkeys(interactions))
            pages.append(
                PRDPage(
                    id=f"page-{i + 1}",
                    title=fr.title,
                    description=fr.description,
                    components=comps,
                    states=states,
                    interactions=interactions,
                    form_fields=form_fields,
                )
            )

        data_model = (
            [DataEntity(name="核心业务数据", fields=parsed.data_fields)] if parsed.data_fields else []
        )
        return PRDDocument(
            title=title,
            summary=funcs[0].description if funcs else parsed.background or "",
            background=parsed.background or "",
            target_users=parsed.target_users,
            functional_requirements=funcs,
            non_functional=parsed.constraints,
            permissions=parsed.permissions,
            data_model=data_model,
            pages=pages,
            acceptance_criteria=parsed.acceptance_criteria,
        )
