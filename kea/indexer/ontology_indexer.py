"""KEA Ontology 索引器 — 扫描、索引、关系图生成.

功能:
1. 扫描 ontology/ 目录下的所有 Markdown 文件
2. 提取 YAML front matter (type, domain, status, tags)
3. 提取 wikilinks [[文档名]] 和 Dataview inline fields (uses:: [[文档]])
4. 构建文档间的关系图
5. 生成 Mermaid 关系图和 Dataview 索引 Markdown
6. 分析单个文档的变更影响范围
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from kea.parser.document_parser import DocumentParser
from kea.parser.models import DocType, KnowledgeDocument


# ---------------------------------------------------------------------------
# 数据模型
# ---------------------------------------------------------------------------

@dataclass
class IndexedDocument:
    """索引后的文档表示."""

    file_path: str = ""
    rel_path: str = ""
    doc_type: str = ""
    id: str = ""
    name: str = ""
    domain: str = ""
    status: str = ""
    tags: list[str] = field(default_factory=list)
    aliases: list[str] = field(default_factory=list)
    english_name: str = ""
    wikilinks: list[str] = field(default_factory=list)
    inline_fields: dict[str, list[str]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "file_path": self.file_path,
            "rel_path": self.rel_path,
            "type": self.doc_type,
            "id": self.id,
            "name": self.name,
            "domain": self.domain,
            "status": self.status,
            "tags": self.tags,
            "aliases": self.aliases,
            "english_name": self.english_name,
            "wikilinks": self.wikilinks,
            "inline_fields": self.inline_fields,
        }


@dataclass
class Relationship:
    """文档之间的关系."""

    source: str = ""
    target: str = ""
    rel_type: str = ""
    cardinality: str = ""
    context: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "target": self.target,
            "type": self.rel_type,
            "cardinality": self.cardinality,
            "context": self.context,
        }


@dataclass
class ImpactReport:
    """变更影响分析报告."""

    target_doc: IndexedDocument | None = None
    incoming: list[dict[str, Any]] = field(default_factory=list)
    outgoing: list[dict[str, Any]] = field(default_factory=list)
    transitive: list[dict[str, Any]] = field(default_factory=list)
    summary: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "target": self.target_doc.to_dict() if self.target_doc else {},
            "incoming": self.incoming,
            "outgoing": self.outgoing,
            "transitive": self.transitive,
            "summary": self.summary,
        }


# ---------------------------------------------------------------------------
# 核心索引器
# ---------------------------------------------------------------------------

class OntologyIndexer:
    """Ontology 知识库索引器."""

    ONTOLOGY_SUBDIRS = ("objects", "logic", "actions", "rules", "domains")
    SEMANTIC_FIELDS = {
        "uses", "produces", "calls", "modifies", "part_of", "contains",
        "related", "follows", "precedes", "instance_of", "triggers",
    }

    def __init__(self, base_dir: str | Path) -> None:
        self.base_dir = Path(base_dir)
        self.documents: list[IndexedDocument] = []
        self.relationships: list[Relationship] = []
        self._doc_by_path: dict[str, IndexedDocument] = {}
        self._doc_by_id: dict[str, IndexedDocument] = {}

    def scan(self) -> None:
        """扫描目录，解析所有 Markdown 文件."""
        self.documents = []
        self.relationships = []
        self._doc_by_path = {}
        self._doc_by_id = {}

        parser = DocumentParser()
        for subdir in self.ONTOLOGY_SUBDIRS:
            subpath = self.base_dir / subdir
            if not subpath.exists():
                continue
            for f in sorted(subpath.glob("*.md")):
                self._index_file(f, parser)

        self.build_graph()

    def _index_file(self, file_path: Path, parser: DocumentParser) -> None:
        """索引单个文件."""
        try:
            doc = parser.parse_file(file_path)
        except Exception:
            doc = self._fallback_parse(file_path)

        rel_path = str(file_path.relative_to(self.base_dir))

        idx = IndexedDocument(
            file_path=str(file_path),
            rel_path=rel_path,
            doc_type=doc.doc_type.value if hasattr(doc.doc_type, "value") else str(doc.doc_type),
            id=doc.id or file_path.stem,
            name=doc.name or file_path.stem,
            domain=doc.domain,
            status=doc.status,
            tags=doc.tags,
            aliases=doc.aliases,
            english_name=doc.english_name,
        )

        raw = file_path.read_text(encoding="utf-8")
        idx.wikilinks = self._extract_wikilinks(raw)
        idx.inline_fields = self._extract_inline_fields(raw)

        self.documents.append(idx)
        self._doc_by_path[rel_path] = idx
        if idx.id:
            self._doc_by_id[idx.id] = idx

    def _fallback_parse(self, file_path: Path) -> KnowledgeDocument:
        """解析失败时的降级处理."""
        raw = file_path.read_text(encoding="utf-8")
        doc = KnowledgeDocument(file_path=str(file_path))

        if raw.strip().startswith("---"):
            parts = raw.split("---", 2)
            if len(parts) >= 3:
                fm = parts[1]
                for line in fm.split("\n"):
                    line_s = line.strip()
                    if line_s.startswith("type:"):
                        v = line_s.split(":", 1)[1].strip().strip('"').strip("'")
                        try:
                            doc.doc_type = DocType(v)
                        except ValueError:
                            pass
                    elif line_s.startswith("id:"):
                        doc.id = line_s.split(":", 1)[1].strip().strip('"').strip("'")
                    elif line_s.startswith("name:"):
                        doc.name = line_s.split(":", 1)[1].strip().strip('"').strip("'")
                    elif line_s.startswith("domain:"):
                        doc.domain = line_s.split(":", 1)[1].strip().strip('"').strip("'")
                    elif line_s.startswith("status:"):
                        doc.status = line_s.split(":", 1)[1].strip().strip('"').strip("'")

        if not doc.id:
            doc.id = file_path.stem
        if not doc.name:
            doc.name = file_path.stem
        return doc

    @staticmethod
    def _extract_wikilinks(text: str) -> list[str]:
        """提取所有 [[文档名]] 链接."""
        pattern = r"\[\[([^\]|]+)(?:\|[^\]]*)?\]\]"
        links = re.findall(pattern, text)
        return [link.strip() for link in links]

    @classmethod
    def _extract_inline_fields(cls, text: str) -> dict[str, list[str]]:
        """提取 Dataview inline fields."""
        result: dict[str, list[str]] = {}
        text_no_code = re.sub(r"```[\s\S]*?```", "", text)

        for field_name in cls.SEMANTIC_FIELDS:
            pattern = rf"(?:^|\n)\s*{re.escape(field_name)}\s*::\s*(.+?)(?:\n|$)"
            matches = re.findall(pattern, text_no_code, re.IGNORECASE)
            for match in matches:
                links = cls._extract_wikilinks(match)
                if links:
                    key = field_name.lower()
                    result.setdefault(key, []).extend(links)

        for key in result:
            result[key] = list(dict.fromkeys(result[key]))

        return result

    def build_graph(self) -> None:
        """构建文档间的关系图.

        关系来源优先级（从强到弱）：
        1. YAML front matter 中的 `relations` 字段（结构化语义关系）
        2. 正文中的 Dataview inline fields（`uses:: [[A]]`）
        3. 正文中的 wikilinks（`[[A]]`，无类型关系）
        """
        self.relationships = []

        # 先从 DocumentParser 的原始结果中加载 relations（最高优先级）
        parser = DocumentParser()
        raw_relations: list[Relationship] = []
        for idx_doc in self.documents:
            try:
                raw_doc = parser.parse_file(idx_doc.file_path)
                for rel in raw_doc.relations:
                    if rel.target:
                        target_doc = self._resolve_link(rel.target)
                        if target_doc and target_doc.rel_path != idx_doc.rel_path:
                            raw_relations.append(Relationship(
                                source=idx_doc.rel_path,
                                target=target_doc.rel_path,
                                rel_type=rel.type or "link",
                                cardinality=rel.cardinality or "",
                                context=f"yaml_relation:{rel.description or ''}",
                            ))
            except Exception:
                pass  # 解析失败则跳过，依赖后续 fallback

        # 收集已有关系的 (source, target) 对，避免低优先级覆盖高优先级
        covered = set()
        for r in raw_relations:
            covered.add((r.source, r.target))
            self.relationships.append(r)

        # 其次：Rule applies_to（转换为 constrains 关系）
        for doc in self.documents:
            raw_doc = self._parse_doc(doc.abs_path)
            if raw_doc and raw_doc.applies_to:
                for item in raw_doc.applies_to:
                    obj_id = item.get("object", "")
                    if obj_id:
                        target_doc = self._resolve_link(obj_id)
                        if target_doc and target_doc.rel_path != doc.rel_path:
                            key = (doc.rel_path, target_doc.rel_path)
                            if key not in covered:
                                covered.add(key)
                                self.relationships.append(Relationship(
                                    source=doc.rel_path,
                                    target=target_doc.rel_path,
                                    rel_type="constrains",
                                    context=f"applies_to:field={item.get('field', '')}",
                                ))

        # 再次：Dataview inline fields
        for doc in self.documents:
            for field_name, targets in doc.inline_fields.items():
                for target_name in targets:
                    target_doc = self._resolve_link(target_name)
                    if target_doc and target_doc.rel_path != doc.rel_path:
                        key = (doc.rel_path, target_doc.rel_path)
                        if key not in covered:
                            covered.add(key)
                            self.relationships.append(Relationship(
                                source=doc.rel_path,
                                target=target_doc.rel_path,
                                rel_type=field_name,
                                context=f"inline_field:{field_name}",
                            ))

        # 最后：wikilinks（仅补充未覆盖的关系）
        for doc in self.documents:
            for link in doc.wikilinks:
                target_doc = self._resolve_link(link)
                if target_doc and target_doc.rel_path != doc.rel_path:
                    key = (doc.rel_path, target_doc.rel_path)
                    if key not in covered:
                        covered.add(key)
                        self.relationships.append(Relationship(
                            source=doc.rel_path,
                            target=target_doc.rel_path,
                            rel_type="link",
                            context="wikilink",
                        ))

        seen = set()
        unique = []
        for r in self.relationships:
            key = (r.source, r.target, r.rel_type)
            if key not in seen:
                seen.add(key)
                unique.append(r)
        self.relationships = unique

    def _resolve_link(self, link_name: str) -> IndexedDocument | None:
        """将链接名称解析为对应的 IndexedDocument."""
        if link_name in self._doc_by_id:
            return self._doc_by_id[link_name]

        for doc in self.documents:
            if doc.name == link_name:
                return doc

        for doc in self.documents:
            if Path(doc.file_path).stem == link_name:
                return doc

        for doc in self.documents:
            if link_name in doc.aliases:
                return doc

        return None

    # ------------------------------------------------------------------
    # 输出
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        """导出完整的索引数据为字典."""
        return {
            "base_dir": str(self.base_dir),
            "total_docs": len(self.documents),
            "total_relationships": len(self.relationships),
            "documents": [d.to_dict() for d in self.documents],
            "relationships": [r.to_dict() for r in self.relationships],
        }

    def to_json(self) -> str:
        """导出为 JSON 字符串."""
        import json
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

    # ------------------------------------------------------------------
    # Mermaid 图生成
    # ------------------------------------------------------------------

    def generate_mermaid_graph(self, scope: str = "global") -> str:
        """生成 Mermaid 关系图.

        Args:
            scope: "global" 生成全局图，或指定 domain 名称生成领域子图
        """
        lines = ["graph TB"]

        # 按领域分组
        domains: dict[str, list[IndexedDocument]] = {}
        other_docs: list[IndexedDocument] = []

        for doc in self.documents:
            if scope != "global" and doc.domain != scope:
                continue
            if doc.domain:
                domains.setdefault(doc.domain, []).append(doc)
            else:
                other_docs.append(doc)

        node_ids: dict[str, str] = {}
        node_counter = 0

        def _node_id(doc: IndexedDocument) -> str:
            if doc.rel_path not in node_ids:
                nonlocal node_counter
                node_counter += 1
                node_ids[doc.rel_path] = f"N{node_counter}"
            return node_ids[doc.rel_path]

        def _node_label(doc: IndexedDocument) -> str:
            prefix = {"object": "📦", "logic": "⚙️", "action": "🔧", "rule": "📋", "domain": "🏛️"}
            icon = prefix.get(doc.doc_type, "📄")
            return f"{icon} {doc.name or doc.id}"

        def _node_style(doc: IndexedDocument) -> str:
            styles = {
                "object": "fill:#f87171,stroke:#dc2626,color:#fff",
                "logic": "fill:#60a5fa,stroke:#2563eb,color:#fff",
                "action": "fill:#4ade80,stroke:#16a34a,color:#000",
                "rule": "fill:#fbbf24,stroke:#d97706,color:#000",
                "domain": "fill:#c084fc,stroke:#9333ea,color:#fff",
            }
            return styles.get(doc.doc_type, "")

        # 生成领域 subgraph
        for domain, docs in sorted(domains.items()):
            safe_domain = re.sub(r"[^\w\u4e00-\u9fff]", "_", domain)
            lines.append(f"    subgraph {safe_domain}[{domain}]")
            for doc in docs:
                nid = _node_id(doc)
                label = _node_label(doc)
                lines.append(f"        {nid}[{label}]")
            lines.append("    end")

        # 无领域的节点
        for doc in other_docs:
            nid = _node_id(doc)
            label = _node_label(doc)
            lines.append(f"    {nid}[{label}]")

        # 生成边
        for rel in self.relationships:
            if rel.source not in node_ids or rel.target not in node_ids:
                continue
            sid = node_ids[rel.source]
            tid = node_ids[rel.target]

            if rel.rel_type == "link":
                lines.append(f"    {sid} --> {tid}")
            else:
                lines.append(f"    {sid} -- {rel.rel_type} --> {tid}")

        # 节点样式
        for doc in self.documents:
            if doc.rel_path not in node_ids:
                continue
            style = _node_style(doc)
            if style:
                nid = node_ids[doc.rel_path]
                lines.append(f"    style {nid} {style}")

        return "\n".join(lines)

    def generate_dataview_index(self) -> str:
        """生成 Dataview 索引 Markdown."""
        lines = [
            "# Ontology 索引",
            "",
            "> 本页由 KEA 自动生成，请勿手动修改。运行 `/ontology-index` 可重新生成。",
            "",
            "---",
            "",
            "## 全局关系图",
            "",
            "```mermaid",
            self.generate_mermaid_graph("global"),
            "```",
            "",
            "---",
            "",
            "## 按领域统计",
            "",
        ]

        domains: dict[str, dict[str, int]] = {}
        for doc in self.documents:
            d = doc.domain or "未分类"
            domains.setdefault(d, {"object": 0, "logic": 0, "action": 0, "rule": 0, "other": 0})
            if doc.doc_type in domains[d]:
                domains[d][doc.doc_type] += 1
            else:
                domains[d]["other"] += 1

        lines.append("| 领域 | 对象 | 逻辑 | 动作 | 规则 | 合计 |")
        lines.append("| --- | ---: | ---: | ---: | ---: | ---: |")
        for domain, counts in sorted(domains.items()):
            total = sum(counts.values())
            lines.append(
                f"| {domain} | {counts['object']} | {counts['logic']} | "
                f"{counts['action']} | {counts['rule']} | {total} |"
            )

        lines.extend([
            "",
            "---",
            "",
            "## 对象列表",
            "",
            "```dataview",
            'TABLE domain, status, file.mtime as "修改时间"',
            'FROM "ontology/objects"',
            'WHERE type = "object"',
            'SORT domain ASC, file.name ASC',
            "```",
            "",
            "## 逻辑列表",
            "",
            "```dataview",
            'TABLE domain, status, file.mtime as "修改时间"',
            'FROM "ontology/logic"',
            'WHERE type = "logic"',
            'SORT domain ASC, file.name ASC',
            "```",
            "",
            "## 动作列表",
            "",
            "```dataview",
            'TABLE domain, status, file.mtime as "修改时间"',
            'FROM "ontology/actions"',
            'WHERE type = "action"',
            'SORT domain ASC, file.name ASC',
            "```",
            "",
            "---",
            "",
            "## 关系统计",
            "",
            f"- 总文档数: {len(self.documents)}",
            f"- 总关系数: {len(self.relationships)}",
            "",
            "### 按关系类型",
            "",
        ])

        rel_types: dict[str, int] = {}
        for rel in self.relationships:
            rel_types[rel.rel_type] = rel_types.get(rel.rel_type, 0) + 1

        for rel_type, count in sorted(rel_types.items(), key=lambda x: -x[1]):
            lines.append(f"- {rel_type}: {count}")

        lines.extend([
            "",
            "### 孤立文档（无任何链接）",
            "",
        ])

        linked_docs = set()
        for rel in self.relationships:
            linked_docs.add(rel.source)
            linked_docs.add(rel.target)

        isolated = [d for d in self.documents if d.rel_path not in linked_docs]
        if isolated:
            for doc in isolated:
                lines.append(f"- [[{doc.name or doc.id}]] ({doc.doc_type})")
        else:
            lines.append("✅ 无孤立文档")

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # 影响分析
    # ------------------------------------------------------------------

    def analyze_impact(self, target: str | Path) -> ImpactReport:
        """分析单个文档的变更影响范围.

        Args:
            target: 目标文档路径（绝对或相对）或文档 ID/名称
        """
        # 解析目标文档
        target_path = str(target)
        target_doc: IndexedDocument | None = None

        # 尝试按路径匹配
        if target_path in self._doc_by_path:
            target_doc = self._doc_by_path[target_path]
        else:
            # 尝试按 ID/名称/文件名匹配
            for doc in self.documents:
                if doc.id == target_path or doc.name == target_path or Path(doc.file_path).name == Path(target_path).name:
                    target_doc = doc
                    break

        if not target_doc:
            # 尝试从文件系统解析
            p = Path(target)
            if p.exists():
                try:
                    rel = str(p.relative_to(self.base_dir))
                    if rel in self._doc_by_path:
                        target_doc = self._doc_by_path[rel]
                except ValueError:
                    pass

        report = ImpactReport()
        if not target_doc:
            report.summary = {"error": f"未找到文档: {target}"}
            return report

        report.target_doc = target_doc

        # 1. 直接影响：incoming（谁引用了我）
        incoming_rels = [r for r in self.relationships if r.target == target_doc.rel_path]
        report.incoming = self._group_by_rel_type(incoming_rels, target_is_sink=True)

        # 2. 直接影响：outgoing（我引用了谁）
        outgoing_rels = [r for r in self.relationships if r.source == target_doc.rel_path]
        report.outgoing = self._group_by_rel_type(outgoing_rels, target_is_sink=False)

        # 3. 传递性影响：二级引用
        transitive: list[dict[str, Any]] = []
        direct_sources = {r.source for r in incoming_rels}
        for src in direct_sources:
            second_level = [r for r in self.relationships if r.target == src]
            for r in second_level:
                if r.source != target_doc.rel_path:
                    doc = self._doc_by_path.get(r.source)
                    if doc:
                        transitive.append({
                            "doc": doc.to_dict(),
                            "via": src,
                            "rel_type": r.rel_type,
                        })

        # 去重
        seen = set()
        unique_transitive = []
        for t in transitive:
            key = t["doc"]["rel_path"]
            if key not in seen:
                seen.add(key)
                unique_transitive.append(t)
        report.transitive = unique_transitive

        # 汇总
        report.summary = {
            "target": target_doc.name or target_doc.id,
            "target_type": target_doc.doc_type,
            "incoming_count": len(incoming_rels),
            "outgoing_count": len(outgoing_rels),
            "transitive_count": len(report.transitive),
            "total_affected": len(set(r.source for r in incoming_rels)) + len(report.transitive),
        }

        return report

    def _group_by_rel_type(self, rels: list[Relationship], target_is_sink: bool = True) -> list[dict[str, Any]]:
        """按关系类型分组.

        Args:
            rels: 关系列表
            target_is_sink: True 表示 rel.target 是目标文档（incoming），
                           False 表示 rel.source 是目标文档（outgoing）
        """
        groups: dict[str, list[IndexedDocument]] = {}
        for rel in rels:
            # incoming: target 是目标文档，source 是引用方
            # outgoing: source 是目标文档，target 是被引用方
            other_path = rel.source if target_is_sink else rel.target
            doc = self._doc_by_path.get(other_path)
            if doc:
                groups.setdefault(rel.rel_type, []).append(doc)

        result = []
        for rel_type, docs in sorted(groups.items()):
            # 去重
            seen = set()
            unique_docs = []
            for d in docs:
                if d.rel_path not in seen:
                    seen.add(d.rel_path)
                    unique_docs.append(d)
            result.append({
                "rel_type": rel_type,
                "count": len(unique_docs),
                "docs": [d.to_dict() for d in unique_docs],
            })
        return result
