"""Markdown Body 解析器 — 提取章节、表格、代码块、链接."""

from __future__ import annotations

import re
from typing import Any

from kea.parser.models import BoundaryCondition, PropertyDef, StateTransition


class MarkdownParser:
    """解析 Markdown Body，提取结构化内容."""

    # 章节标题匹配：支持 # 到 ###，支持中英文冒号
    HEADING_RE = re.compile(r"^(#{1,3})\s+(.+?)[\s:：]*$")

    # Obsidian 链接: [[目标|别名]] 或 [[目标]]
    OBSIDIAN_LINK_RE = re.compile(r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]")

    def extract_sections(self, raw: str) -> dict[str, str]:
        """按标题分块提取章节.

        Returns:
            {章节标题: 章节内容（不含标题行）}
        """
        sections: dict[str, str] = {}
        current_title: str | None = None
        buffer: list[str] = []

        for line in raw.split("\n"):
            m = self.HEADING_RE.match(line)
            if m:
                if current_title is not None:
                    sections[current_title] = "\n".join(buffer).strip()
                current_title = m.group(2).strip()
                buffer = []
            else:
                if current_title is not None:
                    buffer.append(line)

        if current_title is not None:
            sections[current_title] = "\n".join(buffer).strip()

        return sections

    def extract_obsidian_links(self, text: str) -> list[str]:
        """提取 Obsidian 链接的目标 ID 列表（去重）."""
        links = []
        for m in self.OBSIDIAN_LINK_RE.finditer(text):
            target = m.group(1).strip()
            # 去掉 .md 后缀
            target = re.sub(r"\.md$", "", target, flags=re.IGNORECASE)
            if target and target not in links:
                links.append(target)
        return links

    def parse_markdown_table(self, text: str) -> list[dict[str, str]]:
        """解析 Markdown 表格为结构化数组.

        Returns:
            [{列名: 单元格值, ...}, ...]
        """
        lines = [ln for ln in text.split("\n") if ln.strip().startswith("|")]
        if len(lines) < 3:
            return []

        # 表头
        headers = [h.strip() for h in lines[0].split("|")[1:-1]]
        if not headers:
            return []

        # 分隔行检查（第二行必须是 |---|---| 格式）
        if not re.match(r"^\s*\|[\s\-:|]+\|", lines[1]):
            return []

        rows = []
        for line in lines[2:]:
            cells = [c.strip() for c in line.split("|")[1:-1]]
            if len(cells) >= len(headers):
                rows.append({headers[i]: cells[i] for i in range(len(headers))})

        return rows

    def extract_code_blocks(self, text: str, lang: str = "") -> list[str]:
        """提取指定语言的代码块内容.

        Args:
            text: Markdown 文本
            lang: 语言标识，如 "pseudo", "mermaid"。为空则提取所有。
        """
        if lang:
            pattern = rf"```{lang}\n(.*?)```"
        else:
            pattern = r"```(?:\w+)?\n(.*?)```"
        return re.findall(pattern, text, re.DOTALL)

    def parse_property_table(self, text: str) -> list[PropertyDef]:
        """解析对象属性表.

        期望表头: | 名称 | 英文名 | 描述 | 主键 | 类型 | 约束 |
        """
        rows = self.parse_markdown_table(text)
        properties = []
        for row in rows:
            # 支持中英文列名
            name = row.get("名称") or row.get("中文名称") or ""
            english_name = row.get("英文名") or row.get("英文名称") or ""
            description = row.get("描述") or ""
            pk_raw = row.get("主键") or ""
            is_primary_key = pk_raw.strip() in ("是", "yes", "true", "True", "YES")
            type_ = row.get("类型") or ""

            # 约束列（JSON 格式或自然语言）
            constraints = {}
            constraint_text = row.get("约束") or row.get("属性值规则") or ""
            if constraint_text:
                # 尝试解析为 JSON，失败则保留原文
                try:
                    import json

                    constraints = json.loads(constraint_text)
                except (json.JSONDecodeError, ValueError):
                    constraints = {"_raw": constraint_text}

            properties.append(
                PropertyDef(
                    name=name,
                    english_name=english_name,
                    description=description,
                    is_primary_key=is_primary_key,
                    type=type_,
                    constraints=constraints,
                )
            )
        return properties

    def parse_state_transition_table(self, text: str) -> list[StateTransition]:
        """解析状态转换规则表.

        期望表头: | 转换 | 触发条件 | 前置条件 | 执行动作 |
        """
        rows = self.parse_markdown_table(text)
        transitions = []
        for row in rows:
            transition_text = row.get("转换") or ""
            # 格式: "状态A → 状态B"
            states = re.split(r"\s*→\s*", transition_text)
            if len(states) == 2:
                from_state, to_state = states[0].strip(), states[1].strip()
                trigger = row.get("触发条件") or ""
                preconditions = [p.strip() for p in (row.get("前置条件") or "").split(";") if p.strip()]
                actions = [a.strip() for a in (row.get("执行动作") or "").split(";") if a.strip()]
                transitions.append(
                    StateTransition(
                        from_state=from_state,
                        to_state=to_state,
                        trigger=trigger,
                        preconditions=preconditions,
                        actions=actions,
                    )
                )
        return transitions

    def parse_boundary_table(self, text: str) -> list[BoundaryCondition]:
        """解析边界条件矩阵表.

        期望表头: | 场景 | 处理 |
        """
        rows = self.parse_markdown_table(text)
        conditions = []
        for row in rows:
            scenario = row.get("场景") or ""
            handling = row.get("处理") or ""
            if scenario:
                conditions.append(BoundaryCondition(scenario=scenario, handling=handling))
        return conditions

    def parse_input_output_table(self, text: str) -> list[dict[str, str]]:
        """解析输入/输出参数表.

        期望表头: | 参数名称 | 参数类型 | 多值 | 描述 | 示例 |
        """
        return self.parse_markdown_table(text)

    def extract_bullet_items(self, text: str) -> list[str]:
        """提取 Markdown 列表项（支持 - 和 * 和数字）."""
        items = []
        for line in text.split("\n"):
            line = line.strip()
            if re.match(r"^[-*•]\s+", line) or re.match(r"^\d+[.、]\s+", line):
                item = re.sub(r"^[-*•\d.、\s]+", "", line).strip()
                if item:
                    items.append(item)
        return items
