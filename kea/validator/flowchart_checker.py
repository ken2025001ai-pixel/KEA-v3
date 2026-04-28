"""Mermaid 流程图结构校验器 — S1-S4 四项确定性检查."""

from __future__ import annotations

from dataclasses import dataclass, field

from kea.parser.mermaid_parser import MermaidFlowchart, NodeType


@dataclass
class CheckIssue:
    check: str          # "S1" | "S2" | "S3" | "S4"
    node_id: str        # 问题节点 ID，全局问题时为 ""
    node_label: str     # 节点标签
    message: str        # 问题描述


@dataclass
class FlowchartCheckResult:
    file: str = ""
    passed: bool = True
    issues: list[CheckIssue] = field(default_factory=list)


class FlowchartChecker:
    """对单个 MermaidFlowchart 执行 S1-S4 结构校验."""

    def check(self, chart: MermaidFlowchart) -> list[CheckIssue]:
        issues: list[CheckIssue] = []
        issues.extend(self._check_s1(chart))
        issues.extend(self._check_s2(chart))
        issues.extend(self._check_s3(chart))
        issues.extend(self._check_s4(chart))
        return issues

    def _check_s1(self, chart: MermaidFlowchart) -> list[CheckIssue]:
        """S1: 有且仅有 1 个 START 节点."""
        starts = [n for n in chart.nodes if n.node_type == NodeType.START]
        if len(starts) == 0:
            return [CheckIssue("S1", "", "", "流程图缺少开始节点（START）")]
        if len(starts) > 1:
            ids = ", ".join(n.id for n in starts)
            return [CheckIssue("S1", ids, "", f"流程图有 {len(starts)} 个开始节点（需要唯一）：{ids}")]
        return []

    def _check_s2(self, chart: MermaidFlowchart) -> list[CheckIssue]:
        """S2: 至少有 1 个 END 节点."""
        ends = [n for n in chart.nodes if n.node_type == NodeType.END]
        if not ends:
            return [CheckIssue("S2", "", "", "流程图缺少结束节点（END）")]
        return []

    def _check_s3(self, chart: MermaidFlowchart) -> list[CheckIssue]:
        """S3: 每个 DECISION/SUB_DECISION 节点出路 >= 2."""
        issues: list[CheckIssue] = []
        branches = chart.decision_branches()
        for node_id, edges in branches.items():
            if len(edges) < 2:
                node = chart.get_node(node_id)
                label = node.label if node else node_id
                issues.append(CheckIssue(
                    "S3", node_id, label,
                    f"判断节点 \"{label}\" 只有 {len(edges)} 条出路（需要 >= 2）"
                ))
        return issues

    def _check_s4(self, chart: MermaidFlowchart) -> list[CheckIssue]:
        """S4: 无孤立节点（START 外所有节点有入路，END 外所有节点有出路）."""
        issues: list[CheckIssue] = []
        if not chart.nodes:
            return issues

        in_degrees: dict[str, int] = {n.id: 0 for n in chart.nodes}
        out_degrees: dict[str, int] = {n.id: 0 for n in chart.nodes}
        for edge in chart.edges:
            if edge.target in in_degrees:
                in_degrees[edge.target] += 1
            if edge.source in out_degrees:
                out_degrees[edge.source] += 1

        for node in chart.nodes:
            if node.node_type != NodeType.START and in_degrees[node.id] == 0:
                issues.append(CheckIssue(
                    "S4", node.id, node.label,
                    f"节点 \"{node.label}\" 无入路（孤立节点）"
                ))
            if node.node_type != NodeType.END and out_degrees[node.id] == 0:
                issues.append(CheckIssue(
                    "S4", node.id, node.label,
                    f"节点 \"{node.label}\" 无出路（死节点）"
                ))
        return issues
