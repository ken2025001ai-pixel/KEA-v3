"""KEA 核心数据模型 — 知识文档的 AST 表示."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class DocType(str, Enum):
    """知识文档类型."""

    OBJECT = "object"
    LOGIC = "logic"
    ACTION = "action"
    RULE = "rule"


class Severity(str, Enum):
    """问题严重级别."""

    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass
class AgentContext:
    """Agent 理解辅助上下文."""

    one_liner: str = ""
    typical_scenarios: list[str] = field(default_factory=list)
    common_misconceptions: list[str] = field(default_factory=list)
    related_importance: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_yaml(cls, data: dict[str, Any]) -> AgentContext:
        return cls(
            one_liner=data.get("one_liner", ""),
            typical_scenarios=data.get("typical_scenarios", []) or [],
            common_misconceptions=data.get("common_misconceptions", []) or [],
            related_importance=data.get("related_importance", {}) or {},
        )


@dataclass
class Relation:
    """对象/逻辑/动作之间的关系."""

    target: str = ""           # 目标文档 ID
    type: str = ""             # 关系类型: contains/has/belongs_to/uses/calls/modifies/...
    cardinality: str = ""      # "1:1", "1:N", "N:M", "N:1"
    description: str = ""

    @classmethod
    def from_yaml(cls, data: dict[str, Any]) -> Relation:
        return cls(
            target=data.get("target", ""),
            type=data.get("type", ""),
            cardinality=data.get("cardinality", ""),
            description=data.get("description", ""),
        )


@dataclass
class PropertyDef:
    """对象属性定义."""

    name: str = ""             # 中文名称
    english_name: str = ""
    description: str = ""
    is_primary_key: bool = False
    type: str = ""             # 字符串/整数/数值/布尔/枚举/对象引用/...
    constraints: dict[str, Any] = field(default_factory=dict)


@dataclass
class InputParam:
    """Logic/Action 输入参数."""

    name: str = ""
    type: str = ""
    required: bool = True
    description: str = ""
    schema: dict[str, Any] | None = None

    @classmethod
    def from_yaml(cls, data: dict[str, Any]) -> InputParam:
        return cls(
            name=data.get("name", ""),
            type=data.get("type", ""),
            required=data.get("required", True),
            description=data.get("description", ""),
            schema=data.get("schema"),
        )


@dataclass
class OutputParam:
    """Logic/Action 输出参数."""

    name: str = ""
    type: str = ""
    description: str = ""
    unit: str = ""
    schema: dict[str, Any] | None = None

    @classmethod
    def from_yaml(cls, data: dict[str, Any]) -> OutputParam:
        return cls(
            name=data.get("name", ""),
            type=data.get("type", ""),
            description=data.get("description", ""),
            unit=data.get("unit", ""),
            schema=data.get("schema"),
        )


@dataclass
class StateTransition:
    """状态转换定义."""

    from_state: str = ""
    to_state: str = ""
    trigger: str = ""
    preconditions: list[str] = field(default_factory=list)
    actions: list[str] = field(default_factory=list)


@dataclass
class BoundaryCondition:
    """边界条件."""

    scenario: str = ""
    handling: str = ""


@dataclass
class KnowledgeDocument:
    """知识文档的完整 AST 表示 — 这是 KEA 的核心数据模型."""

    # === YAML Front Matter ===
    doc_type: DocType = DocType.OBJECT
    id: str = ""
    name: str = ""
    aliases: list[str] = field(default_factory=list)
    english_name: str = ""
    domain: str = ""           # 所属业务领域
    status: str = ""           # draft | validated | approved
    tags: list[str] = field(default_factory=list)
    agent_context: AgentContext | None = None
    relations: list[Relation] = field(default_factory=list)
    inputs: list[InputParam] = field(default_factory=list)
    outputs: list[OutputParam] = field(default_factory=list)
    # Rule 特有
    category: str = ""         # 规则分类: 状态机约束/数据一致性/计算公式/权限控制
    severity: str = ""         # critical/high/medium/low
    applies_to: list[dict] = field(default_factory=list)
    trigger: str = ""
    rule_expression: str = ""
    error_message: str = ""

    # === Markdown Body Sections ===
    sections: dict[str, str] = field(default_factory=dict)  # {section_title: content}

    # Object 特有
    properties: list[PropertyDef] = field(default_factory=list)
    state_transitions: list[StateTransition] = field(default_factory=list)
    business_rules: list[str] = field(default_factory=list)

    # Logic/Action 特有
    preconditions: list[str] = field(default_factory=list)
    postconditions: list[str] = field(default_factory=list)
    rollback_rules: list[str] = field(default_factory=list)
    boundary_conditions: list[BoundaryCondition] = field(default_factory=list)

    # 代码块
    pseudocode: str = ""               # ```pseudo 内容
    mermaid_diagram: str = ""          # ```mermaid 内容

    # === 文件元数据 ===
    file_path: str = ""
    git_hash: str = ""

    # === 便捷方法 ===

    def get_section(self, title: str) -> str:
        """获取指定章节内容（支持中英文标题模糊匹配）."""
        # 精确匹配
        if title in self.sections:
            return self.sections[title]
        # 模糊匹配
        for key in self.sections:
            if title in key or key in title:
                return self.sections[key]
        return ""

    def relation_targets(self, rel_type: str = "") -> list[str]:
        """获取指定类型的关系目标 ID 列表."""
        if rel_type:
            return [r.target for r in self.relations if r.type == rel_type]
        return [r.target for r in self.relations]

    def is_logic_orchestrator(self) -> bool:
        """判断 Logic 文档是否包含子调用（即是否为编排器）."""
        if self.doc_type != DocType.LOGIC:
            return False
        return any(r.type in ("calls", "uses") for r in self.relations)

    def __repr__(self) -> str:
        return f"KnowledgeDocument({self.doc_type.value}/{self.id}: {self.name})"


# ============================================================================
# 校验相关模型
# ============================================================================

@dataclass
class Issue:
    """校验发现的问题."""

    file: str = ""
    severity: Severity = Severity.WARNING
    category: str = ""       # 问题分类: 结构缺失/链接失效/逻辑缺陷/...
    message: str = ""
    line: int = 0            # 问题所在行号（如适用）
    suggestion: str = ""     # 修复建议

    def to_dict(self) -> dict[str, Any]:
        return {
            "file": self.file,
            "severity": self.severity.value,
            "category": self.category,
            "message": self.message,
            "line": self.line,
            "suggestion": self.suggestion,
        }


@dataclass
class ValidationReport:
    """校验报告."""

    doc_id: str = ""
    doc_name: str = ""
    issues: list[Issue] = field(default_factory=list)
    summary: dict[str, Any] = field(default_factory=dict)

    def error_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == Severity.ERROR)

    def warning_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == Severity.WARNING)

    def info_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == Severity.INFO)

    def has_errors(self) -> bool:
        return self.error_count() > 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "doc_id": self.doc_id,
            "doc_name": self.doc_name,
            "summary": {
                "total": len(self.issues),
                "errors": self.error_count(),
                "warnings": self.warning_count(),
                "infos": self.info_count(),
            },
            "issues": [i.to_dict() for i in self.issues],
        }
