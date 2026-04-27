"""Registry 元数据生成器 — 为每个 OntologySkill 生成 Registry 注册所需的 YAML 元数据."""

from __future__ import annotations

from kea.parser.models import DocType, KnowledgeDocument


class RegistryMetaGenerator:
    """Registry 元数据生成器."""

    def generate(self, doc: KnowledgeDocument, git_hash: str = "") -> str:
        """生成单个 OntologySkill 的 Registry 元数据 YAML.

        Args:
            doc: 知识文档
            git_hash: 知识文档的 git commit hash

        Returns:
            YAML 格式的 Registry 元数据字符串
        """
        lines = [
            f'asset_id: "{doc.id}"',
            f'version: "1.0.0"',
            f'kind: "{self._map_kind(doc.doc_type)}"',
            "",
            "provenance:",
            f'  knowledge_source: "ontology/{doc.doc_type.value}s/{doc.id}.md"',
            f'  knowledge_version: "{git_hash or doc.git_hash or "unknown"}"',
            '  generated_by: "agent:kea-v0.1.0"',
            "",
            "runtime:",
            f'  entrypoint: "{doc.id}"',
            '  language: "python"',
            '  sandbox: "subprocess"',
            "  timeout: 30",
            "",
        ]

        # 依赖
        deps = [f'    - "{r.target}"' for r in doc.relations if r.type in ("calls", "uses")]
        if deps:
            lines.append("  dependencies:")
            lines.extend(deps)
            lines.append("")

        # 前置条件
        if doc.preconditions:
            lines.append("  preconditions:")
            for pre in doc.preconditions:
                lines.append(f'    - "{self._escape_yaml(pre)}"')
            lines.append("")

        # 后置条件
        if doc.postconditions:
            lines.append("  postconditions:")
            for post in doc.postconditions:
                lines.append(f'    - "{self._escape_yaml(post)}"')
            lines.append("")

        # 回滚
        if doc.rollback_rules:
            lines.append('  rollback: "true"')
            lines.append("")

        # 审计
        lines.append("  audit:")
        lines.append('    log_level: "full"')
        lines.append("    retention_days: 365")
        lines.append("")

        # 安全
        lines.append("security:")
        lines.append('  network: "restricted"')
        lines.append('  filesystem: "read-only"')
        lines.append("")

        # 签名（占位）
        lines.append("signature:")
        lines.append('  algorithm: "sha256"')
        lines.append('  value: ""  # 注册时生成')
        lines.append('  signed_by: ""  # 注册时生成')

        return "\n".join(lines)

    def generate_catalog(self, docs: list[KnowledgeDocument]) -> str:
        """生成整个知识库的 Registry 目录 YAML.

        Args:
            docs: 所有已生成的 OntologySkill 对应的知识文档

        Returns:
            YAML 格式的目录索引
        """
        lines = [
            "# KEA Registry Catalog",
            "",
            "assets:",
        ]

        for doc in docs:
            if doc.doc_type in (DocType.ACTION, DocType.LOGIC):
                lines.append(f"  - asset_id: \"{doc.id}\"")
                lines.append(f"    kind: {self._map_kind(doc.doc_type)}")
                lines.append(f"    version: \"1.0.0\"")
                lines.append(f"    name: \"{doc.name}\"")
                lines.append("")

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # 辅助方法
    # ------------------------------------------------------------------

    def _map_kind(self, doc_type: DocType) -> str:
        """映射文档类型到 Registry kind."""
        mapping = {
            DocType.ACTION: "skill",
            DocType.LOGIC: "skill",
            DocType.OBJECT: "schema",
            DocType.RULE: "rule",
        }
        return mapping.get(doc_type, "unknown")

    def _escape_yaml(self, text: str) -> str:
        """转义 YAML 字符串中的特殊字符."""
        return text.replace('"', '\\"').replace("\n", " ")
