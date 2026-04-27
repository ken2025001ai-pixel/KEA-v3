"""状态机校验器 — 检查状态机的可达性、死状态、不可达状态.

使用图论算法分析 Mermaid 状态机图：
- 可达性分析（DFS/BFS）
- 死状态检测（无出边且非终止状态）
- 不可达状态检测（从起始状态无法到达）
- 终止状态一致性检查
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from kea.parser.models import Issue, KnowledgeDocument, Severity, ValidationReport


class StateValidator:
    """状态机图论校验器."""

    def __init__(self) -> None:
        pass

    def validate(self, doc: KnowledgeDocument) -> ValidationReport:
        """校验单个文档的状态机."""
        report = ValidationReport(doc_id=doc.id, doc_name=doc.name)

        # 只有 Object 类型可能有状态机
        if not doc.state_transitions and not doc.mermaid_diagram:
            return report

        # 构建状态图
        graph = self._build_state_graph(doc)
        if not graph.states:
            return report

        report.issues.extend(self._check_unreachable_states(graph))
        report.issues.extend(self._check_dead_states(graph))
        report.issues.extend(self._check_missing_transitions(graph, doc))
        report.issues.extend(self._check_mermaid_consistency(doc, graph))

        report.summary = {
            "total_issues": len(report.issues),
            "errors": report.error_count(),
            "warnings": report.warning_count(),
            "state_count": len(graph.states),
            "transition_count": len(graph.transitions),
            "unreachable_states": len(graph.get_unreachable_states()),
            "dead_states": len(graph.get_dead_states()),
        }

        return report

    # ------------------------------------------------------------------
    # 状态图构建
    # ------------------------------------------------------------------

    def _build_state_graph(self, doc: KnowledgeDocument) -> StateGraph:
        """从状态转换规则构建状态图."""
        graph = StateGraph()

        # 从 state_transitions 构建
        for t in doc.state_transitions:
            graph.add_transition(t.from_state, t.to_state, t.trigger)

        # 从 Mermaid 图补充（如果解析得出）
        if doc.mermaid_diagram:
            mermaid_transitions = self._parse_mermaid_transitions(doc.mermaid_diagram)
            for from_state, to_state, trigger in mermaid_transitions:
                if not graph.has_transition(from_state, to_state):
                    graph.add_transition(from_state, to_state, trigger)

        return graph

    def _parse_mermaid_transitions(self, mermaid: str) -> list[tuple[str, str, str]]:
        """从 Mermaid stateDiagram-v2 解析状态转换.

        格式: stateA --> stateB: trigger
        """
        transitions = []
        for line in mermaid.split("\n"):
            line = line.strip()
            # 匹配: stateA --> stateB: trigger
            match = re.match(r"(\S+)\s*-->\s*(\S+)\s*[:：]?\s*(.*)", line)
            if match:
                from_state, to_state, trigger = match.groups()
                transitions.append((from_state, to_state, trigger.strip()))
        return transitions

    # ------------------------------------------------------------------
    # 图论检查
    # ------------------------------------------------------------------

    def _check_unreachable_states(self, graph: StateGraph) -> list[Issue]:
        """检查不可达状态（从 [*] 或初始状态无法到达）."""
        issues = []
        unreachable = graph.get_unreachable_states()

        for state in unreachable:
            if state == "[*]":
                continue
            issues.append(
                Issue(
                    severity=Severity.WARNING,
                    category="状态机-不可达状态",
                    message=f"状态「{state}」从起始状态无法到达",
                    suggestion="检查状态转换规则，确保每个状态都有从起始状态到达的路径",
                )
            )

        return issues

    def _check_dead_states(self, graph: StateGraph) -> list[Issue]:
        """检查死状态（非终止状态但无出边）."""
        issues = []
        dead = graph.get_dead_states()

        for state in dead:
            if state == "[*]":
                continue
            issues.append(
                Issue(
                    severity=Severity.WARNING,
                    category="状态机-死状态",
                    message=f"状态「{state}」没有出边转换（非终止状态的死胡同）",
                    suggestion="为状态「{}」添加转换到其他状态的路径，或将其标记为终止状态".format(state),
                )
            )

        return issues

    def _check_missing_transitions(self, graph: StateGraph, doc: KnowledgeDocument) -> list[Issue]:
        """检查状态转换规则中是否有遗漏的常见转换."""
        issues = []

        # 检查是否有默认/兜底转换（从每个非终止状态）
        for state in graph.states:
            if state == "[*]":
                continue
            outgoing = graph.get_outgoing(state)
            if outgoing:
                # 检查是否有明确的错误/异常分支
                has_error_branch = any(
                    re.search(r"错误|异常|失败|超时|不足|非法|拒绝", t.trigger, re.IGNORECASE)
                    for t in outgoing
                )
                if not has_error_branch and len(outgoing) == 1:
                    issues.append(
                        Issue(
                            severity=Severity.INFO,
                            category="状态机-分支完整性",
                            message=f"状态「{state}」只有一个出边转换，建议考虑错误/异常分支",
                        )
                    )

        return issues

    def _check_mermaid_consistency(self, doc: KnowledgeDocument, graph: StateGraph) -> list[Issue]:
        """检查 Mermaid 图与状态转换规则表是否一致."""
        issues = []

        if not doc.mermaid_diagram or not doc.state_transitions:
            return issues

        # 从 Mermaid 解析的状态
        mermaid_transitions = self._parse_mermaid_transitions(doc.mermaid_diagram)
        mermaid_pairs = {(f, t) for f, t, _ in mermaid_transitions}
        table_pairs = {(t.from_state, t.to_state) for t in doc.state_transitions}

        # 检查 Mermaid 中有但表中没有的转换
        for from_state, to_state, trigger in mermaid_transitions:
            if (from_state, to_state) not in table_pairs and from_state != "[*]" and to_state != "[*]":
                issues.append(
                    Issue(
                        severity=Severity.INFO,
                        category="状态机-一致性",
                        message=f"Mermaid 图中有「{from_state} → {to_state}」转换，但状态转换规则表中没有",
                        suggestion="在「状态转换规则」表中补充此转换",
                    )
                )

        # 检查表中有但 Mermaid 中没有的转换
        for t in doc.state_transitions:
            if (t.from_state, t.to_state) not in mermaid_pairs and t.from_state != "[*]" and t.to_state != "[*]":
                issues.append(
                    Issue(
                        severity=Severity.INFO,
                        category="状态机-一致性",
                        message=f"状态转换规则表中有「{t.from_state} → {t.to_state}」转换，但 Mermaid 图中没有",
                        suggestion="在 Mermaid 状态机图中补充此转换",
                    )
                )

        return issues


# ============================================================================
# 状态图数据结构
# ============================================================================

class StateGraph:
    """状态机图（有向图）."""

    def __init__(self) -> None:
        self.transitions: list[Transition] = []
        self.states: set[str] = set()
        self._adj: dict[str, list[Transition]] = {}  # from_state -> [transitions]
        self._reverse_adj: dict[str, list[Transition]] = {}  # to_state -> [transitions]

    def add_transition(self, from_state: str, to_state: str, trigger: str) -> None:
        t = Transition(from_state, to_state, trigger)
        self.transitions.append(t)
        self.states.add(from_state)
        self.states.add(to_state)
        self._adj.setdefault(from_state, []).append(t)
        self._reverse_adj.setdefault(to_state, []).append(t)

    def has_transition(self, from_state: str, to_state: str) -> bool:
        return any(t.from_state == from_state and t.to_state == to_state for t in self.transitions)

    def get_outgoing(self, state: str) -> list[Transition]:
        return self._adj.get(state, [])

    def get_incoming(self, state: str) -> list[Transition]:
        return self._reverse_adj.get(state, [])

    def get_unreachable_states(self) -> list[str]:
        """获取从起始状态不可达的状态."""
        # 找到起始状态（[*] → state 中的 state，或没有入边的状态）
        start_states = set()
        for t in self.transitions:
            if t.from_state == "[*]":
                start_states.add(t.to_state)

        # 如果没有 [*] 标记，找没有入边（除了 [*]）的状态作为起始
        if not start_states:
            for state in self.states:
                incoming = [t for t in self.get_incoming(state) if t.from_state != "[*]"]
                if not incoming and state != "[*]":
                    start_states.add(state)

        if not start_states:
            # 如果没有明确的起始状态，默认第一个状态
            non_special = [s for s in self.states if s != "[*]"]
            if non_special:
                start_states.add(non_special[0])

        # BFS 遍历可达状态
        reachable = set()
        queue = list(start_states)
        while queue:
            current = queue.pop(0)
            if current in reachable:
                continue
            reachable.add(current)
            for t in self.get_outgoing(current):
                if t.to_state not in reachable:
                    queue.append(t.to_state)

        return sorted([s for s in self.states if s not in reachable and s != "[*]"])

    def get_dead_states(self) -> list[str]:
        """获取死状态（非终止状态且无出边）."""
        dead = []
        for state in self.states:
            if state == "[*]":
                continue
            outgoing = self.get_outgoing(state)
            # 终止状态（有到 [*] 的转换）不算死状态
            is_terminal = any(t.to_state == "[*]" for t in outgoing)
            if not outgoing and not is_terminal:
                dead.append(state)
        return sorted(dead)


@dataclass
class Transition:
    """状态转换."""

    from_state: str
    to_state: str
    trigger: str
