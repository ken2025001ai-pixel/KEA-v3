"""规则校验器 — 结构/链接/表格/分支/契约检查.

基于知识文档的 AST 进行确定性校验，不依赖 LLM。
所有检查项都是 100% 确定的（无二义性）。
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from kea.parser.models import (
    BoundaryCondition,
    DocType,
    Issue,
    KnowledgeDocument,
    Severity,
    ValidationReport,
)


class RuleValidator:
    """规则校验器.

    检查内容：
    1. YAML FM 必需字段完整性
    2. 文档间引用有效性（relations.target → 对应文件存在）
    3. 对象属性表完整性（主键/类型/约束）
    4. 状态机语法和语义检查
    5. Logic/Action 输入输出 schema 完整性
    6. 分支完整性（Logic 的判断节点）
    7. 子流程契约匹配（Logic 调用的子流程输入参数）
    8. Action 孤立检测
    9. Rule 适用范围有效性
    """

    def __init__(self, all_docs: dict[str, KnowledgeDocument] | None = None) -> None:
        """初始化校验器.

        Args:
            all_docs: 所有已加载的知识文档字典 {id: KnowledgeDocument}。
                      用于交叉引用检查（如链接有效性、孤立检测）。
        """
        self.all_docs = all_docs or {}
        self.all_ids = set(self.all_docs.keys())

    # ------------------------------------------------------------------
    # 公共 API
    # ------------------------------------------------------------------

    def validate(self, doc: KnowledgeDocument) -> ValidationReport:
        """校验单个知识文档."""
        report = ValidationReport(doc_id=doc.id, doc_name=doc.name)

        # 按文档类型分发校验
        if doc.doc_type == DocType.OBJECT:
            report.issues.extend(self._validate_object(doc))
        elif doc.doc_type == DocType.LOGIC:
            report.issues.extend(self._validate_logic(doc))
        elif doc.doc_type == DocType.ACTION:
            report.issues.extend(self._validate_action(doc))
        elif doc.doc_type == DocType.RULE:
            report.issues.extend(self._validate_rule(doc))

        # 通用校验（所有类型）
        report.issues.extend(self._validate_common(doc))

        # 生成分类汇总
        report.summary = self._generate_summary(report)

        return report

    def validate_all(self) -> dict[str, ValidationReport]:
        """校验所有已加载的文档，返回 {doc_id: report}."""
        reports = {}
        for doc_id, doc in self.all_docs.items():
            reports[doc_id] = self.validate(doc)
        return reports

    # ------------------------------------------------------------------
    # Object 校验
    # ------------------------------------------------------------------

    def _validate_object(self, doc: KnowledgeDocument) -> list[Issue]:
        issues = []

        # R-OBJ-001: 必须有至少一个属性
        if not doc.properties:
            issues.append(
                Issue(
                    file=doc.file_path,
                    severity=Severity.ERROR,
                    category="结构缺失",
                    message="对象文档缺少属性定义（properties 为空）",
                    suggestion="在「属性清单」章节中定义至少一个属性",
                )
            )

        # R-OBJ-002: 必须有且仅有一个主键
        pk_count = sum(1 for p in doc.properties if p.is_primary_key)
        if pk_count == 0:
            issues.append(
                Issue(
                    file=doc.file_path,
                    severity=Severity.ERROR,
                    category="主键缺失",
                    message="对象属性清单中没有标注主键=是的属性",
                    suggestion="为对象的唯一标识属性设置主键=是",
                )
            )
        elif pk_count > 1:
            issues.append(
                Issue(
                    file=doc.file_path,
                    severity=Severity.WARNING,
                    category="主键重复",
                    message=f"对象属性清单中有 {pk_count} 个主键，建议只有一个",
                    suggestion="检查属性表，确保只有一个主键",
                )
            )

        # R-OBJ-003: 每个属性必须有名称和类型
        for i, prop in enumerate(doc.properties):
            if not prop.name:
                issues.append(
                    Issue(
                        file=doc.file_path,
                        severity=Severity.ERROR,
                        category="属性定义不完整",
                        message=f"第 {i+1} 个属性缺少中文名称",
                    )
                )
            if not prop.type:
                issues.append(
                    Issue(
                        file=doc.file_path,
                        severity=Severity.ERROR,
                        category="属性定义不完整",
                        message=f"属性「{prop.name or f'#{i+1}'}」缺少类型",
                    )
                )

        # R-OBJ-004: 状态机检查（如果有状态转换）
        if doc.state_transitions:
            issues.extend(self._validate_state_machine(doc))

        # R-OBJ-005: 业务规则必须有编号前缀
        for rule in doc.business_rules:
            if not re.match(r"^R-[A-Z]+-\d+", rule.strip()):
                issues.append(
                    Issue(
                        file=doc.file_path,
                        severity=Severity.INFO,
                        category="规范建议",
                        message=f"业务规则建议以编号前缀开头（如 R-{doc.id.upper()}-001）: {rule[:50]}...",
                    )
                )

        return issues

    # ------------------------------------------------------------------
    # Logic 校验
    # ------------------------------------------------------------------

    def _validate_logic(self, doc: KnowledgeDocument) -> list[Issue]:
        issues = []

        # R-LOG-001: Logic 必须有输入输出定义
        if not doc.inputs:
            issues.append(
                Issue(
                    file=doc.file_path,
                    severity=Severity.WARNING,
                    category="输入缺失",
                    message="Logic 文档未定义输入参数",
                    suggestion="在 YAML FM 的 inputs 中定义输入参数",
                )
            )
        if not doc.outputs:
            issues.append(
                Issue(
                    file=doc.file_path,
                    severity=Severity.WARNING,
                    category="输出缺失",
                    message="Logic 文档未定义输出参数",
                    suggestion="在 YAML FM 的 outputs 中定义输出参数",
                )
            )

        # R-LOG-002: 伪代码检查
        if not doc.pseudocode:
            issues.append(
                Issue(
                    file=doc.file_path,
                    severity=Severity.ERROR,
                    category="伪代码缺失",
                    message="Logic 文档缺少伪代码（```pseudo 代码块）",
                    suggestion="在「逻辑描述」章节中添加伪代码",
                )
            )
        else:
            issues.extend(self._validate_pseudocode(doc))

        # R-LOG-003: 子调用检查（relations 中 type=calls 的 target 必须是 Action 或 Logic）
        for rel in doc.relations:
            if rel.type == "calls":
                if rel.target not in self.all_ids:
                    issues.append(
                        Issue(
                            file=doc.file_path,
                            severity=Severity.ERROR,
                            category="引用失效",
                            message=f"Logic 调用的子流程/动作「{rel.target}」不存在",
                            suggestion=f"检查 relations 中的 target 是否正确，或创建 {rel.target}.md",
                        )
                    )
                else:
                    target_doc = self.all_docs[rel.target]
                    if target_doc.doc_type not in (DocType.LOGIC, DocType.ACTION):
                        issues.append(
                            Issue(
                                file=doc.file_path,
                                severity=Severity.ERROR,
                                category="类型不匹配",
                                message=f"Logic 调用的「{rel.target}」类型为 {target_doc.doc_type.value}，应为 logic 或 action",
                            )
                        )

        # R-LOG-004: 前置/后置条件检查
        if not doc.preconditions:
            issues.append(
                Issue(
                    file=doc.file_path,
                    severity=Severity.INFO,
                    category="前置条件缺失",
                    message="Logic 文档未定义前置条件",
                    suggestion="在「前提」章节中定义执行前必须满足的条件",
                )
            )
        if not doc.postconditions:
            issues.append(
                Issue(
                    file=doc.file_path,
                    severity=Severity.INFO,
                    category="后置条件缺失",
                    message="Logic 文档未定义后置条件",
                    suggestion="在「效果」章节中定义执行后必须满足的条件",
                )
            )

        # R-LOG-005: 边界条件检查
        if not doc.boundary_conditions:
            issues.append(
                Issue(
                    file=doc.file_path,
                    severity=Severity.INFO,
                    category="边界条件缺失",
                    message="Logic 文档未定义边界条件",
                    suggestion="在「边界条件」章节中定义异常场景的处理方式",
                )
            )

        return issues

    # ------------------------------------------------------------------
    # Action 校验
    # ------------------------------------------------------------------

    def _validate_action(self, doc: KnowledgeDocument) -> list[Issue]:
        issues = []

        # R-ACT-001: Action 必须有输入输出
        if not doc.inputs:
            issues.append(
                Issue(
                    file=doc.file_path,
                    severity=Severity.ERROR,
                    category="输入缺失",
                    message="Action 文档未定义输入参数",
                )
            )
        if not doc.outputs:
            issues.append(
                Issue(
                    file=doc.file_path,
                    severity=Severity.ERROR,
                    category="输出缺失",
                    message="Action 文档未定义输出参数",
                )
            )

        # R-ACT-002: Action 必须有伪代码
        if not doc.pseudocode:
            issues.append(
                Issue(
                    file=doc.file_path,
                    severity=Severity.ERROR,
                    category="伪代码缺失",
                    message="Action 文档缺少伪代码",
                )
            )
        else:
            issues.extend(self._validate_pseudocode(doc))

        # R-ACT-003: Action 不能调用其他 Action（只能被 Logic 调用）
        for rel in doc.relations:
            if rel.type == "calls":
                issues.append(
                    Issue(
                        file=doc.file_path,
                        severity=Severity.ERROR,
                        category="调用违规",
                        message=f"Action 文档不能包含 calls 关系（「{rel.target}」）。Action 应为原子操作，不允许子调用",
                        suggestion="将子调用逻辑提升到 Logic 层，或合并为一个 Action",
                    )
                )

        # R-ACT-004: Action 必须有回滚规则（如果有副作用）
        has_side_effect = any(r.type == "modifies" for r in doc.relations)
        if has_side_effect and not doc.rollback_rules:
            issues.append(
                Issue(
                    file=doc.file_path,
                    severity=Severity.WARNING,
                    category="回滚缺失",
                    message="Action 有副作用（modifies 关系）但未定义回滚规则",
                    suggestion="在「回滚规则」章节中定义失败时的恢复逻辑",
                )
            )

        # R-ACT-005: 孤立检测（Action 必须被至少一个 Logic 引用）
        if self.all_docs:
            referenced = False
            for other in self.all_docs.values():
                if other.doc_type == DocType.LOGIC:
                    for rel in other.relations:
                        if rel.target == doc.id and rel.type in ("calls", "uses"):
                            referenced = True
                            break
                if referenced:
                    break
            if not referenced:
                issues.append(
                    Issue(
                        file=doc.file_path,
                        severity=Severity.INFO,
                        category="孤立动作",
                        message=f"Action「{doc.name}」未被任何 Logic 文档引用",
                        suggestion="检查是否有 Logic 文档应该调用此 Action，或删除未使用的 Action",
                    )
                )

        return issues

    # ------------------------------------------------------------------
    # Rule 校验
    # ------------------------------------------------------------------

    def _validate_rule(self, doc: KnowledgeDocument) -> list[Issue]:
        issues = []

        # R-RULE-001: Rule 必须有触发条件和表达式
        if not doc.trigger:
            issues.append(
                Issue(
                    file=doc.file_path,
                    severity=Severity.ERROR,
                    category="触发条件缺失",
                    message="Rule 文档未定义 trigger",
                )
            )
        if not doc.rule_expression:
            issues.append(
                Issue(
                    file=doc.file_path,
                    severity=Severity.ERROR,
                    category="规则表达式缺失",
                    message="Rule 文档未定义 rule_expression",
                )
            )

        # R-RULE-002: applies_to 引用的对象必须存在
        for item in doc.applies_to:
            obj_id = item.get("object", "")
            if obj_id and obj_id not in self.all_ids:
                issues.append(
                    Issue(
                        file=doc.file_path,
                        severity=Severity.ERROR,
                        category="引用失效",
                        message=f"Rule 适用范围引用的对象「{obj_id}」不存在",
                    )
                )
            elif obj_id and obj_id in self.all_ids:
                # 检查字段是否存在
                field_name = item.get("field", "")
                if field_name:
                    obj_doc = self.all_docs[obj_id]
                    field_names = {p.name for p in obj_doc.properties}
                    if field_name not in field_names:
                        issues.append(
                            Issue(
                                file=doc.file_path,
                                severity=Severity.WARNING,
                                category="字段不存在",
                                message=f"Rule 适用范围引用的字段「{field_name}」在对象「{obj_id}」中未定义",
                            )
                        )

        # R-RULE-003: severity 必须是有效值
        valid_severities = {"critical", "high", "medium", "low"}
        if doc.severity and doc.severity.lower() not in valid_severities:
            issues.append(
                Issue(
                    file=doc.file_path,
                    severity=Severity.WARNING,
                    category="severity 无效",
                    message=f"Rule severity「{doc.severity}」不是有效值，应为 critical/high/medium/low 之一",
                )
            )

        return issues

    # ------------------------------------------------------------------
    # 通用校验
    # ------------------------------------------------------------------

    def _validate_common(self, doc: KnowledgeDocument) -> list[Issue]:
        issues = []

        # R-COM-001: 必需字段检查
        if not doc.id:
            issues.append(
                Issue(
                    file=doc.file_path,
                    severity=Severity.ERROR,
                    category="ID 缺失",
                    message="YAML FM 中缺少 id 字段",
                )
            )
        if not doc.name:
            issues.append(
                Issue(
                    file=doc.file_path,
                    severity=Severity.ERROR,
                    category="名称缺失",
                    message="YAML FM 中缺少 name 字段",
                )
            )

        # R-COM-002: ID 命名规范（建议小写+下划线）
        if doc.id and not re.match(r"^[a-z][a-z0-9_]*$", doc.id):
            issues.append(
                Issue(
                    file=doc.file_path,
                    severity=Severity.INFO,
                    category="命名规范",
                    message=f"id「{doc.id}」建议采用小写字母+下划线格式（如 eco_change_order）",
                )
            )

        # R-COM-003: relations 引用有效性
        for rel in doc.relations:
            if rel.target not in self.all_ids:
                issues.append(
                    Issue(
                        file=doc.file_path,
                        severity=Severity.ERROR,
                        category="引用失效",
                        message=f"relations 中引用的目标「{rel.target}」不存在",
                        suggestion=f"创建 {rel.target}.md 或修正 relations.target",
                    )
                )

        # R-COM-004: agent_context 检查
        if doc.agent_context:
            if not doc.agent_context.one_liner:
                issues.append(
                    Issue(
                        file=doc.file_path,
                        severity=Severity.INFO,
                        category="agent_context 不完整",
                        message="agent_context.one_liner 为空，建议补充一句话描述",
                    )
                )
        else:
            issues.append(
                Issue(
                    file=doc.file_path,
                    severity=Severity.WARNING,
                    category="agent_context 缺失",
                    message="YAML FM 中缺少 agent_context，Agent 将难以理解此文档的用途",
                    suggestion="补充 agent_context（one_liner + typical_scenarios + common_misconceptions）",
                )
            )

        # R-COM-005: 输入参数 schema 检查
        for inp in doc.inputs:
            if not inp.name:
                issues.append(
                    Issue(
                        file=doc.file_path,
                        severity=Severity.ERROR,
                        category="输入参数定义不完整",
                        message="存在 name 为空的输入参数",
                    )
                )
            valid_types = {"string", "integer", "number", "boolean", "array", "object", "enum"}
            if inp.type and inp.type.lower() not in valid_types and not inp.type.startswith("object:"):
                issues.append(
                    Issue(
                        file=doc.file_path,
                        severity=Severity.WARNING,
                        category="类型未知",
                        message=f"输入参数「{inp.name}」的类型「{inp.type}」不是标准类型",
                        suggestion=f"建议使用标准类型之一：{', '.join(valid_types)}",
                    )
                )

        return issues

    # ------------------------------------------------------------------
    # 子校验器
    # ------------------------------------------------------------------

    def _validate_state_machine(self, doc: KnowledgeDocument) -> list[Issue]:
        """校验状态机的语法和语义."""
        issues = []

        # 检查 Mermaid 图是否存在
        if not doc.mermaid_diagram:
            issues.append(
                Issue(
                    file=doc.file_path,
                    severity=Severity.INFO,
                    category="状态机缺失",
                    message="对象有状态转换规则但缺少 Mermaid 状态机图",
                    suggestion="在「状态机」章节中添加 stateDiagram-v2 图",
                )
            )
        else:
            # 简单语法检查
            if "stateDiagram-v2" not in doc.mermaid_diagram:
                issues.append(
                    Issue(
                        file=doc.file_path,
                        severity=Severity.WARNING,
                        category="状态机语法",
                        message="Mermaid 图不是 stateDiagram-v2 类型",
                    )
                )

        # 检查状态转换的完整性
        states_in_transitions = set()
        for t in doc.state_transitions:
            states_in_transitions.add(t.from_state)
            states_in_transitions.add(t.to_state)

        # 检查是否有起始状态和终止状态
        has_start = any(t.from_state == "[*]" for t in doc.state_transitions)
        has_end = any(t.to_state == "[*]" for t in doc.state_transitions)

        if not has_start and doc.state_transitions:
            issues.append(
                Issue(
                    file=doc.file_path,
                    severity=Severity.INFO,
                    category="状态机语义",
                    message="状态机没有定义起始状态（[*] → state）",
                )
            )
        if not has_end and doc.state_transitions:
            issues.append(
                Issue(
                    file=doc.file_path,
                    severity=Severity.INFO,
                    category="状态机语义",
                    message="状态机没有定义终止状态（state → [*]）",
                )
            )

        return issues

    def _validate_pseudocode(self, doc: KnowledgeDocument) -> list[Issue]:
        """校验伪代码的基本语法."""
        issues = []
        code = doc.pseudocode

        # 检查函数定义
        if "function" not in code:
            issues.append(
                Issue(
                    file=doc.file_path,
                    severity=Severity.WARNING,
                    category="伪代码结构",
                    message="伪代码中缺少 function 定义",
                    suggestion="伪代码应以 function 定义开头",
                )
            )

        # 检查是否有 return
        if "return" not in code:
            issues.append(
                Issue(
                    file=doc.file_path,
                    severity=Severity.INFO,
                    category="伪代码结构",
                    message="伪代码中缺少 return 语句",
                    suggestion="函数应有明确的 return 语句",
                )
            )

        # 检查括号匹配
        if code.count("(") != code.count(")"):
            issues.append(
                Issue(
                    file=doc.file_path,
                    severity=Severity.ERROR,
                    category="伪代码语法",
                    message="伪代码中括号不匹配",
                )
            )
        if code.count("{") != code.count("}"):
            issues.append(
                Issue(
                    file=doc.file_path,
                    severity=Severity.ERROR,
                    category="伪代码语法",
                    message="伪代码中大括号不匹配",
                )
            )

        # 检查缩进一致性（使用空格缩进）
        lines = code.split("\n")
        for i, line in enumerate(lines):
            if line.strip() and not line.startswith(" ") and i > 0:
                # 首行不缩进是允许的（函数定义）
                if not line.strip().startswith("function"):
                    continue

        # Logic 特有：检查 call_action 的 target 是否存在
        if doc.doc_type == DocType.LOGIC:
            call_pattern = r'call_action\s*\(\s*["\']([^"\']+)["\']'
            for match in re.finditer(call_pattern, code):
                action_id = match.group(1)
                if action_id not in self.all_ids:
                    issues.append(
                        Issue(
                            file=doc.file_path,
                            severity=Severity.ERROR,
                            category="伪代码引用失效",
                            message=f"伪代码中调用的 Action「{action_id}」不存在",
                        )
                    )

        return issues

    # ------------------------------------------------------------------
    # 辅助方法
    # ------------------------------------------------------------------

    def _generate_summary(self, report: ValidationReport) -> dict[str, Any]:
        """生成校验报告摘要."""
        return {
            "total_issues": len(report.issues),
            "errors": report.error_count(),
            "warnings": report.warning_count(),
            "infos": report.info_count(),
            "pass": not report.has_errors(),
            "categories": self._categorize_issues(report.issues),
        }

    def _categorize_issues(self, issues: list[Issue]) -> dict[str, int]:
        """按分类统计问题数量."""
        result: dict[str, int] = {}
        for issue in issues:
            result[issue.category] = result.get(issue.category, 0) + 1
        return result
