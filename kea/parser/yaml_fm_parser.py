"""YAML Front Matter 解析器 — 纯 Python 实现，零外部依赖.

只处理知识文档需要的 YAML 子集：
- 标量：字符串、数字、布尔值
- 列表：[item1, item2] 或 - item1\n- item2
- 字典：key: value 或嵌套字典
"""

from __future__ import annotations

import json
import re
from typing import Any

from kea.parser.models import (
    AgentContext,
    DocType,
    InputParam,
    KnowledgeDocument,
    OutputParam,
    Relation,
)


class YAMLFMParserError(Exception):
    """YAML Front Matter 解析错误."""

    pass


class YAMLFMParser:
    """解析知识文档的 YAML Front Matter 部分."""

    def parse(self, raw: str, file_path: str = "") -> tuple[KnowledgeDocument, str]:
        """解析 YAML Front Matter.

        Returns:
            (KnowledgeDocument with YAML fields populated, raw markdown body)
        """
        doc = KnowledgeDocument(file_path=file_path)
        body = raw

        # 检查是否有 YAML Front Matter
        if raw.strip().startswith("---"):
            parts = raw.split("---", 2)
            if len(parts) >= 3:
                yaml_text = parts[1].strip()
                body = parts[2].strip()
                try:
                    data = self._parse_yaml(yaml_text)
                except Exception as e:
                    raise YAMLFMParserError(f"YAML 解析失败: {e}") from e

                self._populate(doc, data)

        return doc, body

    # ------------------------------------------------------------------
    # 轻量级 YAML 解析器
    # ------------------------------------------------------------------

    def _parse_yaml(self, text: str) -> dict[str, Any]:
        """将 YAML 文本解析为 Python 字典.

        这是一个简化版解析器，只处理知识文档中常见的 YAML 结构。
        """
        lines = text.split("\n")
        result: dict[str, Any] = {}
        i = 0
        while i < len(lines):
            line = lines[i]
            stripped = line.rstrip()
            if not stripped or stripped.startswith("#"):
                i += 1
                continue

            # 计算当前行的缩进
            indent = len(line) - len(line.lstrip())

            # 解析键值对
            if ":" in stripped:
                key, value = self._split_key_value(stripped)
                key = key.strip()

                # 检查是否是列表开始（下一行以 - 开头且缩进更大）
                if i + 1 < len(lines):
                    next_line = lines[i + 1]
                    next_indent = len(next_line) - len(next_line.lstrip())
                    next_stripped = next_line.strip()
                    if next_stripped.startswith("-") and next_indent > indent:
                        # 解析列表
                        items, consumed = self._parse_list(lines, i + 1, indent)
                        result[key] = items
                        i += 1 + consumed
                        continue

                # 检查是否是嵌套字典（下一行缩进更大且不是列表）
                if i + 1 < len(lines) and not value.strip():
                    next_line = lines[i + 1]
                    next_indent = len(next_line) - len(next_line.lstrip())
                    next_stripped = next_line.strip()
                    if next_indent > indent and not next_stripped.startswith("-") and ":" in next_stripped:
                        nested, consumed = self._parse_dict(lines, i + 1, indent)
                        result[key] = nested
                        i += 1 + consumed
                        continue

                # 普通值
                result[key] = self._parse_value(value.strip())

            i += 1

        return result

    def _split_key_value(self, line: str) -> tuple[str, str]:
        """分割键值对，处理字符串中的冒号."""
        # 简单方案：找到第一个不在引号中的冒号
        in_quote = False
        quote_char = None
        for i, ch in enumerate(line):
            if ch in ('"', "'"):
                if not in_quote:
                    in_quote = True
                    quote_char = ch
                elif quote_char == ch:
                    in_quote = False
                    quote_char = None
            elif ch == ":" and not in_quote:
                return line[:i], line[i + 1:]
        return line, ""

    def _parse_value(self, value: str) -> Any:
        """解析单个 YAML 值."""
        value = value.strip()
        if not value:
            return None

        # 字符串引号
        if (value.startswith('"') and value.endswith('"')) or \
           (value.startswith("'") and value.endswith("'")):
            return value[1:-1]

        # 列表内联 [a, b, c]
        if value.startswith("[") and value.endswith("]"):
            return self._parse_inline_list(value[1:-1])

        # 布尔值
        if value.lower() in ("true", "yes", "on"):
            return True
        if value.lower() in ("false", "no", "off"):
            return False

        # 数字
        if re.match(r"^-?\d+$", value):
            return int(value)
        if re.match(r"^-?\d+\.\d+$", value):
            return float(value)

        # 字符串
        return value

    def _parse_inline_list(self, text: str) -> list[Any]:
        """解析内联列表 [a, b, c]."""
        items = []
        current = ""
        in_quote = False
        quote_char = None
        for ch in text:
            if ch in ('"', "'"):
                if not in_quote:
                    in_quote = True
                    quote_char = ch
                elif quote_char == ch:
                    in_quote = False
                    quote_char = None
                current += ch
            elif ch == "," and not in_quote:
                items.append(self._parse_value(current))
                current = ""
            else:
                current += ch
        if current.strip():
            items.append(self._parse_value(current))
        return items

    def _parse_list(self, lines: list[str], start: int, parent_indent: int) -> tuple[list[Any], int]:
        """解析块级列表.

        Returns:
            (列表项, 消耗的行数)
        """
        items = []
        i = start
        while i < len(lines):
            line = lines[i]
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                i += 1
                continue

            indent = len(line) - len(line.lstrip())
            if indent <= parent_indent and not stripped.startswith("-"):
                break

            if stripped.startswith("-"):
                # 提取列表项内容（去掉开头的 -）
                item_text = stripped[1:].strip()
                item_indent = indent

                # 情况 1: 空列表项 + 后续嵌套内容 → 嵌套字典或列表
                if not item_text and i + 1 < len(lines):
                    next_indent = len(lines[i + 1]) - len(lines[i + 1].lstrip())
                    if next_indent > item_indent:
                        nested, consumed = self._parse_dict(lines, i + 1, item_indent)
                        items.append(nested)
                        i += 1 + consumed
                        continue

                # 情况 2: 列表项包含 : → 可能是单行字典或后续有嵌套属性
                if ":" in item_text:
                    # 先作为单行字典解析
                    single_dict = self._parse_inline_dict(item_text)

                    # 检查后续行是否有更大缩进（多行字典属性）
                    if i + 1 < len(lines):
                        next_line = lines[i + 1]
                        next_indent = len(next_line) - len(next_line.lstrip())
                        next_stripped = next_line.strip()
                        if next_indent > item_indent and not next_stripped.startswith("-") and ":" in next_stripped:
                            # 后续是多行字典属性
                            nested, consumed = self._parse_dict(lines, i + 1, item_indent)
                            single_dict.update(nested)
                            items.append(single_dict)
                            i += 1 + consumed
                            continue

                    items.append(single_dict)
                    i += 1
                    continue

                # 情况 3: 普通值
                items.append(self._parse_value(item_text))

            i += 1

        return items, i - start

    def _parse_inline_dict(self, text: str) -> dict[str, Any]:
        """解析单行字典文本 'key: value' 或 '{key1: val1, key2: val2}'.

        支持 YAML 内联对象格式 {k1: v1, k2: v2}。
        """
        result: dict[str, Any] = {}
        text = text.strip()

        # 处理花括号包裹的内联字典: {k1: v1, k2: v2}
        if text.startswith("{") and text.endswith("}"):
            inner = text[1:-1]
            # 按逗号分割，但要处理引号内的逗号
            pairs = self._split_inline_dict_items(inner)
            for pair in pairs:
                pair = pair.strip()
                if not pair:
                    continue
                if ":" in pair:
                    key, value = self._split_key_value(pair)
                    result[key.strip()] = self._parse_value(value.strip())
            return result

        # 普通 key: value
        if ":" in text:
            key, value = self._split_key_value(text)
            result[key.strip()] = self._parse_value(value.strip())
        return result

    def _split_inline_dict_items(self, text: str) -> list[str]:
        """按逗号分割内联字典项，处理引号内的逗号."""
        items = []
        current = ""
        in_quote = False
        quote_char = None
        depth = 0  # 花括号嵌套深度

        for ch in text:
            if ch in ('"', "'"):
                if not in_quote:
                    in_quote = True
                    quote_char = ch
                elif quote_char == ch:
                    in_quote = False
                current += ch
            elif ch == "{" and not in_quote:
                depth += 1
                current += ch
            elif ch == "}" and not in_quote:
                depth -= 1
                current += ch
            elif ch == "," and not in_quote and depth == 0:
                items.append(current)
                current = ""
            else:
                current += ch

        if current.strip():
            items.append(current)
        return items

    def _parse_dict(self, lines: list[str], start: int, parent_indent: int) -> tuple[dict[str, Any], int]:
        """解析嵌套字典.

        Returns:
            (字典, 消耗的行数)
        """
        result: dict[str, Any] = {}
        i = start
        while i < len(lines):
            line = lines[i]
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                i += 1
                continue

            indent = len(line) - len(line.lstrip())
            if indent <= parent_indent:
                break

            if ":" in stripped:
                key, value = self._split_key_value(stripped)
                key = key.strip()
                value = value.strip()

                # 检查嵌套
                if not value and i + 1 < len(lines):
                    next_line = lines[i + 1]
                    next_indent = len(next_line) - len(next_line.lstrip())
                    next_stripped = next_line.strip()
                    if next_indent > indent:
                        if next_stripped.startswith("-"):
                            items, consumed = self._parse_list(lines, i + 1, indent)
                            result[key] = items
                            i += 1 + consumed
                            continue
                        else:
                            nested, consumed = self._parse_dict(lines, i + 1, indent)
                            result[key] = nested
                            i += 1 + consumed
                            continue

                result[key] = self._parse_value(value)

            i += 1

        return result, i - start

    # ------------------------------------------------------------------
    # 填充 KnowledgeDocument
    # ------------------------------------------------------------------

    def _populate(self, doc: KnowledgeDocument, data: dict[str, Any]) -> None:
        """将解析后的 YAML 数据填充到 KnowledgeDocument."""
        if "type" in data:
            try:
                doc.doc_type = DocType(data["type"])
            except ValueError:
                raise YAMLFMParserError(f"未知的文档类型: {data['type']}")

        doc.id = data.get("id", "")
        doc.name = data.get("name", "")
        doc.aliases = data.get("aliases", []) or []
        doc.english_name = data.get("english_name", "")
        doc.domain = data.get("domain", "")
        doc.version = data.get("version", "")
        doc.status = data.get("status", "")
        doc.tags = data.get("tags", []) or []

        if "agent_context" in data:
            doc.agent_context = AgentContext.from_yaml(data["agent_context"])

        if "relations" in data:
            doc.relations = [Relation.from_yaml(r) for r in data["relations"]]

        if "inputs" in data:
            doc.inputs = [InputParam.from_yaml(i) for i in data["inputs"]]
        if "outputs" in data:
            doc.outputs = [OutputParam.from_yaml(o) for o in data["outputs"]]

        doc.category = data.get("category", "")
        doc.rule_type = data.get("rule_type", "")
        doc.severity = data.get("severity", "")
        doc.applies_to = data.get("applies_to", []) or []
        doc.trigger = data.get("trigger", "")
        doc.rule_expression = data.get("rule_expression", "")
        doc.error_message = data.get("error_message", "")
