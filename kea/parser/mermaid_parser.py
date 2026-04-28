"""Mermaid 流程图解析器 — 从 Mermaid 文本提取结构化流程信息."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class NodeType(str, Enum):
    START = "start"
    END = "end"
    ACTION = "action"
    ACTIVITY = "activity"
    DECISION = "decision"
    SUBPROCESS = "subprocess"
    SUB_DECISION = "sub_decision"
    RECURSIVE = "recursive"
    UNKNOWN = "unknown"


@dataclass
class MermaidNode:
    id: str = ""
    label: str = ""
    node_type: NodeType = NodeType.UNKNOWN
    raw_shape: str = ""


@dataclass
class MermaidEdge:
    source: str = ""
    target: str = ""
    label: str = ""


@dataclass
class MermaidSubgraph:
    name: str = ""
    nodes: list[str] = field(default_factory=list)


@dataclass
class MermaidFlowchart:
    title: str = ""
    direction: str = "TD"
    nodes: list[MermaidNode] = field(default_factory=list)
    edges: list[MermaidEdge] = field(default_factory=list)
    subgraphs: list[MermaidSubgraph] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "direction": self.direction,
            "nodes": [{"id": n.id, "label": n.label, "type": n.node_type.value} for n in self.nodes],
            "edges": [{"source": e.source, "target": e.target, "label": e.label} for e in self.edges],
            "subgraphs": [{"name": s.name, "nodes": s.nodes} for s in self.subgraphs],
        }

    def decision_branches(self) -> dict[str, list[MermaidEdge]]:
        decisions = {n.id: [] for n in self.nodes if n.node_type in (NodeType.DECISION, NodeType.SUB_DECISION)}
        for edge in self.edges:
            if edge.source in decisions:
                decisions[edge.source].append(edge)
        return decisions

    def get_node(self, node_id: str) -> MermaidNode | None:
        for n in self.nodes:
            if n.id == node_id:
                return n
        return None


# 匹配节点定义
NODE_RE = re.compile(
    r'([A-Za-z0-9_\u4e00-\u9fa5]+)'
    r'(\[\[.*?\]\]|\{\{.*?\}\}|\(\(.*?\)\)|\[.*?\]|\{.*?\}|\(.*?\)|>[^\]]*\])'
)


def _extract_label(shape: str) -> str:
    if shape.startswith("((") and shape.endswith("))"):
        return shape[2:-2].strip()
    if shape.startswith("[[") and shape.endswith("]]"):
        return shape[2:-2].strip()
    if shape.startswith("{{") and shape.endswith("}}"):
        return shape[2:-2].strip()
    if shape.startswith(">") and shape.endswith("]"):
        return shape[1:-1].strip()
    return shape[1:-1].strip()


def _detect_type(shape: str, label: str) -> NodeType:
    if shape.startswith("((") and shape.endswith("))"):
        if any(kw in label for kw in ("开始", "Start", "启动", "入口")):
            return NodeType.START
        if any(kw in label for kw in ("结束", "End", "终止", "出口", "完成")):
            return NodeType.END
        return NodeType.UNKNOWN
    if shape.startswith(">") and shape.endswith("]"):
        return NodeType.END
    # 注意：{{ 必须在 { 之前检查
    if shape.startswith("{{") and shape.endswith("}}"):
        if any(kw in label for kw in ("循环", "递归", "重复", "重新")):
            return NodeType.RECURSIVE
        return NodeType.SUB_DECISION
    if shape.startswith("{") and shape.endswith("}"):
        return NodeType.DECISION
    if shape.startswith("[[") and shape.endswith("]]"):
        return NodeType.SUBPROCESS
    if shape.startswith("(") and shape.endswith(")"):
        return NodeType.ACTIVITY
    if shape.startswith("[") and shape.endswith("]"):
        return NodeType.ACTION
    return NodeType.UNKNOWN


def _parse_nodes(line: str) -> dict[str, MermaidNode]:
    """从一行中提取所有节点定义."""
    nodes: dict[str, MermaidNode] = {}
    for m in NODE_RE.finditer(line):
        nid = m.group(1)
        shape = m.group(2)
        label = _extract_label(shape)
        nodes[nid] = MermaidNode(id=nid, label=label, node_type=_detect_type(shape, label), raw_shape=shape)
    return nodes


def _parse_edges(line: str) -> list[MermaidEdge]:
    """从一行中提取所有边."""
    edges: list[MermaidEdge] = []

    # 1. 将节点定义替换为占位符
    def repl(m: re.Match) -> str:
        return f"__NODE_{m.group(1)}__"
    simplified = NODE_RE.sub(repl, line)

    # 2. 将 -->|标签| 替换为 --LABEL:标签-->
    # Mermaid 语法: A -->|label| B
    simplified = re.sub(r'-->(\s*)\|([^|]+)\|', r'--LABEL:\2-->', simplified)

    # 3. 按 --> 分割
    parts = simplified.split('-->')

    # 解析每个 segment 为 (node_id, outgoing_label)
    segments: list[tuple[str, str]] = []
    for part in parts:
        part = part.strip()
        if not part:
            continue

        # 提取 LABEL
        label = ""
        label_match = re.search(r'--LABEL:([^-]+)$', part)
        if label_match:
            label = label_match.group(1).strip()
            part = part[:label_match.start()].strip()

        # 提取节点 ID
        if part.startswith("__NODE_"):
            node_id = part[7:].rstrip("_")
        else:
            node_id = part.strip()

        segments.append((node_id, label))

    # 创建边：第 i 个 segment 到第 i+1 个 segment
    # 标签来自第 i 个 segment 的 label（因为替换时把标签放在了 source 后面）
    for i in range(len(segments) - 1):
        src, label = segments[i]
        tgt, _ = segments[i + 1]
        edges.append(MermaidEdge(source=src, target=tgt, label=label))

    return edges


def parse_mermaid(content: str) -> MermaidFlowchart:
    chart = MermaidFlowchart()
    lines = [line.strip() for line in content.split("\n") if line.strip() and not line.strip().startswith("%%")]

    if not lines:
        return chart

    first = lines[0]
    m = re.match(r'^(?:flowchart|graph)\s+(TD|LR|BT|RL)(?:\s+\((.+?)\))?', first, re.IGNORECASE)
    if m:
        chart.direction = m.group(1).upper()
        if m.group(2):
            chart.title = m.group(2).strip()

    node_defs: dict[str, MermaidNode] = {}
    all_edges: list[MermaidEdge] = []
    current_sg: MermaidSubgraph | None = None

    for line in lines[1:]:
        sg = re.match(r'^\s*subgraph\s+(.+?)\s*$', line, re.IGNORECASE)
        if sg:
            current_sg = MermaidSubgraph(name=sg.group(1).strip())
            continue
        if re.match(r'^\s*end\s*$', line, re.IGNORECASE):
            if current_sg:
                chart.subgraphs.append(current_sg)
                current_sg = None
            continue

        line_nodes = _parse_nodes(line)
        node_defs.update(line_nodes)
        if current_sg:
            for nid in line_nodes:
                current_sg.nodes.append(nid)

        line_edges = _parse_edges(line)
        all_edges.extend(line_edges)

    # 补充裸 ID 节点（只在边中出现、没有形状定义的节点）
    for edge in all_edges:
        for nid in (edge.source, edge.target):
            if nid and nid not in node_defs:
                node_defs[nid] = MermaidNode(id=nid, label=nid, node_type=NodeType.UNKNOWN)

    chart.nodes = list(node_defs.values())
    chart.edges = all_edges
    return chart


def parse_file(path: str) -> MermaidFlowchart:
    with open(path, encoding="utf-8") as f:
        content = f.read()
    m = re.search(r'```mermaid\s*\n(.*?)```', content, re.DOTALL)
    if m:
        content = m.group(1)
    return parse_mermaid(content)
