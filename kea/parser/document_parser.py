"""知识文档主解析器 — 整合 YAML FM + Markdown Body 解析."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Any

from kea.parser.markdown_parser import MarkdownParser
from kea.parser.models import (
    BoundaryCondition,
    DocType,
    KnowledgeDocument,
    StateTransition,
)
from kea.parser.yaml_fm_parser import YAMLFMParser, YAMLFMParserError


class DocumentParserError(Exception):
    """文档解析错误."""

    pass


class DocumentParser:
    """知识文档解析器 — 将 Markdown 文件解析为 KnowledgeDocument AST.

    使用方式:
        parser = DocumentParser()
        doc = parser.parse_file("ontology/objects/ECO变更单.md")
        print(doc.id, doc.name)
        print(doc.properties)
    """

    def __init__(self) -> None:
        self.yaml_parser = YAMLFMParser()
        self.md_parser = MarkdownParser()

    # ------------------------------------------------------------------
    # 公共 API
    # ------------------------------------------------------------------

    def parse_file(self, file_path: str | Path) -> KnowledgeDocument:
        """解析单个 Markdown 文件."""
        path = Path(file_path)
        if not path.exists():
            raise DocumentParserError(f"文件不存在: {path}")

        raw = path.read_text(encoding="utf-8")
        doc = self.parse_text(raw, str(path))
        doc.file_path = str(path)

        # 尝试获取 git hash
        try:
            doc.git_hash = self._get_git_hash(path)
        except Exception:
            doc.git_hash = ""

        return doc

    def parse_directory(self, directory: str | Path) -> list[KnowledgeDocument]:
        """解析目录下的所有知识文档.

        自动遍历 objects/, logic/, actions/, rules/ 子目录。
        """
        dir_path = Path(directory)
        docs: list[KnowledgeDocument] = []

        for subdir in ("objects", "logic", "actions", "rules"):
            subpath = dir_path / subdir
            if subpath.exists():
                for f in sorted(subpath.glob("*.md")):
                    try:
                        docs.append(self.parse_file(f))
                    except (DocumentParserError, YAMLFMParserError) as e:
                        # 记录错误但继续解析其他文件
                        print(f"⚠️  解析失败 {f}: {e}")

        return docs

    def parse_text(self, raw: str, file_path: str = "") -> KnowledgeDocument:
        """从原始文本解析知识文档."""
        # Step 1: 解析 YAML Front Matter
        doc, body = self.yaml_parser.parse(raw, file_path)

        # Step 2: 解析 Markdown Body
        self._parse_body(doc, body)

        return doc

    # ------------------------------------------------------------------
    # 内部方法
    # ------------------------------------------------------------------

    def _parse_body(self, doc: KnowledgeDocument, body: str) -> None:
        """解析 Markdown Body，填充文档的各个 section."""
        # 提取章节
        sections = self.md_parser.extract_sections(body)
        doc.sections = sections

        # 提取代码块
        doc.pseudocode = self._extract_pseudocode(body)
        doc.mermaid_diagram = self._extract_mermaid(body)

        # 根据文档类型解析特定 section
        if doc.doc_type == DocType.OBJECT:
            self._parse_object_sections(doc, sections)
        elif doc.doc_type == DocType.LOGIC:
            self._parse_logic_sections(doc, sections)
        elif doc.doc_type == DocType.ACTION:
            self._parse_action_sections(doc, sections)
        elif doc.doc_type == DocType.RULE:
            self._parse_rule_sections(doc, sections)

    def _parse_object_sections(self, doc: KnowledgeDocument, sections: dict[str, str]) -> None:
        """解析 Object 特有 section."""
        # 属性清单
        for title in ("属性清单", "对象属性清单", "业务属性清单"):
            if title in sections:
                doc.properties = self.md_parser.parse_property_table(sections[title])
                break

        # 状态转换规则
        for title in ("状态转换规则", "状态转换"):
            if title in sections:
                doc.state_transitions = self.md_parser.parse_state_transition_table(sections[title])
                break

        # 业务规则
        for title in ("业务规则", "规则"):
            if title in sections:
                doc.business_rules = self.md_parser.extract_bullet_items(sections[title])
                break

    def _parse_logic_sections(self, doc: KnowledgeDocument, sections: dict[str, str]) -> None:
        """解析 Logic 特有 section."""
        # 前置条件
        for title in ("前提", "前置条件"):
            if title in sections:
                doc.preconditions = self.md_parser.extract_bullet_items(sections[title])
                break

        # 后置条件
        for title in ("效果", "后置条件"):
            if title in sections:
                doc.postconditions = self.md_parser.extract_bullet_items(sections[title])
                break

        # 回滚规则（可能是自然语言段落 + 伪代码，不是列表项）
        for title in ("回滚规则", "回滚"):
            if title in sections:
                # 先尝试提取列表项，如果没有则取整个文本（去掉伪代码块）
                bullets = self.md_parser.extract_bullet_items(sections[title])
                if bullets:
                    doc.rollback_rules = bullets
                else:
                    # 去掉伪代码块，保留自然语言描述
                    text = sections[title]
                    text = re.sub(r'```pseudo\n.*?```', '', text, flags=re.DOTALL).strip()
                    if text:
                        doc.rollback_rules = [text]
                break

        # 边界条件
        for title in ("边界条件", "边界"):
            if title in sections:
                doc.boundary_conditions = self.md_parser.parse_boundary_table(sections[title])
                break

    def _parse_action_sections(self, doc: KnowledgeDocument, sections: dict[str, str]) -> None:
        """解析 Action 特有 section — 与 Logic 相同."""
        self._parse_logic_sections(doc, sections)

        # Action 额外可能有触发条件
        for title in ("触发条件", "触发"):
            if title in sections:
                # 触发条件通常只有一个，作为列表第一项
                trigger_items = self.md_parser.extract_bullet_items(sections[title])
                if trigger_items and not doc.preconditions:
                    doc.preconditions = trigger_items
                break

    def _parse_rule_sections(self, doc: KnowledgeDocument, sections: dict[str, str]) -> None:
        """解析 Rule 特有 section."""
        # Rule 的大部分内容在 YAML FM 中，Body 通常只有规则表达式和说明
        pass

    def _extract_pseudocode(self, body: str) -> str:
        """提取伪代码块内容."""
        blocks = self.md_parser.extract_code_blocks(body, lang="pseudo")
        return "\n\n".join(blocks) if blocks else ""

    def _extract_mermaid(self, body: str) -> str:
        """提取 Mermaid 代码块内容."""
        blocks = self.md_parser.extract_code_blocks(body, lang="mermaid")
        return blocks[0] if blocks else ""

    def _get_git_hash(self, path: Path) -> str:
        """获取文件最近的 git commit hash."""
        result = subprocess.run(
            ["git", "log", "-1", "--format=%H", "--", str(path)],
            capture_output=True,
            text=True,
            cwd=path.parent if path.is_file() else path,
        )
        return result.stdout.strip() if result.returncode == 0 else ""


# ------------------------------------------------------------------
# 便捷函数
# ------------------------------------------------------------------

def parse_file(path: str | Path) -> KnowledgeDocument:
    """便捷函数：解析单个文件."""
    return DocumentParser().parse_file(path)


def parse_directory(directory: str | Path) -> list[KnowledgeDocument]:
    """便捷函数：解析目录."""
    return DocumentParser().parse_directory(directory)
