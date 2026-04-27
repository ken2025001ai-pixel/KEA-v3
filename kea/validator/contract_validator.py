"""契约校验器 — 检查 YAML FM 中的前置/后置/回滚条件是否在伪代码中有对应实现.

核心思想：
- 前置条件（preconditions）应该在伪代码中以 assert 形式出现
- 后置条件（postconditions）应该在伪代码的 return 附近出现
- 回滚规则（rollback_rules）应该在伪代码中以 rollback 函数形式出现
"""

from __future__ import annotations

import re
from typing import Any

from kea.parser.models import DocType, Issue, KnowledgeDocument, Severity, ValidationReport


class ContractValidator:
    """契约覆盖校验器.

    检查知识文档中声明的契约（前置/后置/回滚）是否在伪代码中有对应的实现。
    这是一个"半确定性"检查 —— 可以确认明显缺失的契约，但无法 100% 确认
    自然语言描述是否被伪代码完全覆盖（这部分需要 LLM 辅助）。
    """

    def __init__(self, all_docs: dict[str, KnowledgeDocument] | None = None) -> None:
        self.all_docs = all_docs or {}

    def validate(self, doc: KnowledgeDocument) -> ValidationReport:
        """校验单个文档的契约覆盖."""
        report = ValidationReport(doc_id=doc.id, doc_name=doc.name)

        if doc.doc_type not in (DocType.LOGIC, DocType.ACTION):
            return report

        report.issues.extend(self._check_preconditions(doc))
        report.issues.extend(self._check_postconditions(doc))
        report.issues.extend(self._check_rollback(doc))
        report.issues.extend(self._check_input_output_usage(doc))

        report.summary = {
            "total_issues": len(report.issues),
            "errors": report.error_count(),
            "warnings": report.warning_count(),
            "infos": report.info_count(),
            "precondition_coverage": self._calculate_precondition_coverage(doc),
            "postcondition_coverage": self._calculate_postcondition_coverage(doc),
        }

        return report

    # ------------------------------------------------------------------
    # 前置条件检查
    # ------------------------------------------------------------------

    def _check_preconditions(self, doc: KnowledgeDocument) -> list[Issue]:
        """检查前置条件是否在伪代码中有 assert 对应."""
        issues = []
        code = doc.pseudocode

        for pre in doc.preconditions:
            # 提取关键词（去掉连接词）
            keywords = self._extract_keywords(pre)

            # 检查伪代码中是否有包含这些关键词的 assert
            found = False
            for keyword in keywords:
                # 匹配 assert 语句中包含关键词
                pattern = rf'assert\s+.*{re.escape(keyword)}.*'
                if re.search(pattern, code, re.IGNORECASE):
                    found = True
                    break

            if not found:
                issues.append(
                    Issue(
                        file=doc.file_path,
                        severity=Severity.WARNING,
                        category="契约覆盖-前置条件",
                        message=f"前置条件「{pre}」在伪代码中没有对应的 assert 检查",
                        suggestion=f"在伪代码中添加 assert 语句验证此条件，如: assert ..., \"{pre}\"",
                    )
                )

        return issues

    # ------------------------------------------------------------------
    # 后置条件检查
    # ------------------------------------------------------------------

    def _check_postconditions(self, doc: KnowledgeDocument) -> list[Issue]:
        """检查后置条件是否在伪代码的 return 附近有体现."""
        issues = []
        code = doc.pseudocode

        for post in doc.postconditions:
            keywords = self._extract_keywords(post)

            # 后置条件通常出现在 return 附近或函数末尾
            # 简化检查：看关键词是否出现在伪代码中
            found = False
            for keyword in keywords:
                if keyword.lower() in code.lower():
                    found = True
                    break

            if not found:
                issues.append(
                    Issue(
                        file=doc.file_path,
                        severity=Severity.WARNING,
                        category="契约覆盖-后置条件",
                        message=f"后置条件「{post}」在伪代码中没有明显体现",
                        suggestion="在伪代码的 return 语句前添加对后置条件的验证或赋值",
                    )
                )

        return issues

    # ------------------------------------------------------------------
    # 回滚检查
    # ------------------------------------------------------------------

    def _check_rollback(self, doc: KnowledgeDocument) -> list[Issue]:
        """检查回滚规则是否在伪代码中有 rollback 函数."""
        issues = []
        code = doc.pseudocode

        if not doc.rollback_rules:
            return issues

        # 检查是否有 rollback 函数定义
        has_rollback_func = "function rollback" in code or "def rollback" in code

        if not has_rollback_func:
            issues.append(
                Issue(
                    file=doc.file_path,
                    severity=Severity.WARNING,
                    category="契约覆盖-回滚",
                    message="文档定义了回滚规则，但伪代码中没有 rollback 函数",
                    suggestion="在伪代码中添加 function rollback(...) 定义",
                )
            )

        return issues

    # ------------------------------------------------------------------
    # 输入输出参数使用检查
    # ------------------------------------------------------------------

    def _check_input_output_usage(self, doc: KnowledgeDocument) -> list[Issue]:
        """检查输入参数是否在伪代码中被使用，输出参数是否被赋值."""
        issues = []
        code = doc.pseudocode

        # 检查输入参数是否被使用
        for inp in doc.inputs:
            if not inp.name:
                continue
            # 输入参数应该在伪代码中被引用（作为变量或函数参数）
            name_pattern = rf'\b{re.escape(inp.name)}\b'
            if not re.search(name_pattern, code, re.IGNORECASE):
                issues.append(
                    Issue(
                        file=doc.file_path,
                        severity=Severity.WARNING,
                        category="参数未使用",
                        message=f"输入参数「{inp.name}」在伪代码中未被引用",
                        suggestion=f"在伪代码中使用参数 {inp.name}，或从 inputs 中移除",
                    )
                )

        # 检查输出参数是否被赋值/返回
        for out in doc.outputs:
            if not out.name:
                continue
            # 输出参数应该在 return 语句中
            if "return" in code:
                return_section = code[code.rfind("return"):]
                if out.name not in return_section:
                    issues.append(
                        Issue(
                            file=doc.file_path,
                            severity=Severity.WARNING,
                            category="输出未返回",
                            message=f"输出参数「{out.name}」没有在 return 语句中返回",
                            suggestion=f"确保 return 语句包含 {out.name}",
                        )
                    )

        return issues

    # ------------------------------------------------------------------
    # 覆盖率计算
    # ------------------------------------------------------------------

    def _calculate_precondition_coverage(self, doc: KnowledgeDocument) -> float:
        """计算前置条件覆盖率（0.0 - 1.0）."""
        if not doc.preconditions:
            return 1.0

        covered = 0
        code = doc.pseudocode
        for pre in doc.preconditions:
            keywords = self._extract_keywords(pre)
            for keyword in keywords:
                pattern = rf'assert\s+.*{re.escape(keyword)}.*'
                if re.search(pattern, code, re.IGNORECASE):
                    covered += 1
                    break

        return covered / len(doc.preconditions)

    def _calculate_postcondition_coverage(self, doc: KnowledgeDocument) -> float:
        """计算后置条件覆盖率（0.0 - 1.0）."""
        if not doc.postconditions:
            return 1.0

        covered = 0
        code = doc.pseudocode
        for post in doc.postconditions:
            keywords = self._extract_keywords(post)
            for keyword in keywords:
                if keyword.lower() in code.lower():
                    covered += 1
                    break

        return covered / len(doc.postconditions)

    # ------------------------------------------------------------------
    # 辅助方法
    # ------------------------------------------------------------------

    def _extract_keywords(self, text: str) -> list[str]:
        """从自然语言文本中提取关键词（用于匹配伪代码）.

        策略：
        1. 去掉停用词（的/是/在/等）
        2. 保留名词性短语（通常 2-6 个字符）
        3. 保留英文标识符
        """
        stopwords = {"的", "是", "在", "和", "或", "为", "有", "无", "不", "需", "要",
                     "必须", "应该", "可以", "需要", "如果", "当", "且", "与"}

        keywords = []

        # 保留引号内的精确字符串
        for match in re.finditer(r'["\']([^"\']+)["\']', text):
            keywords.append(match.group(1))

        # 保留英文标识符（属性名、变量名）
        for match in re.finditer(r'[a-zA-Z_][a-zA-Z0-9_.]*', text):
            word = match.group()
            if len(word) >= 2 and word.lower() not in stopwords:
                keywords.append(word)

        # 保留中文名词（2-6 字）
        for match in re.finditer(r'[\u4e00-\u9fa5]{2,6}', text):
            word = match.group()
            if word not in stopwords:
                keywords.append(word)

        # 去重并保持顺序
        seen = set()
        result = []
        for k in keywords:
            if k not in seen:
                seen.add(k)
                result.append(k)

        return result
