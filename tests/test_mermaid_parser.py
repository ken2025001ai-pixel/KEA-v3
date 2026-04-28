"""mermaid_parser.parse_file 单元测试."""
from kea.parser.mermaid_parser import parse_file


class TestParseFileMd:
    def test_md_with_frontmatter_and_mermaid_block(self, tmp_path):
        """含 YAML front matter 的 .md 文件，应正确提取 Mermaid 代码块。"""
        f = tmp_path / "flowchart.md"
        f.write_text(
            "---\ntitle: 测试流程图\n---\n\n# 标题\n\n```mermaid\nflowchart TD\n"
            "  A[采购订单] --> B[供应商]\n```\n",
            encoding="utf-8",
        )
        chart = parse_file(str(f))
        labels = {n.label for n in chart.nodes}
        assert "采购订单" in labels
        assert "供应商" in labels

    def test_md_without_mermaid_block_falls_back(self, tmp_path):
        """不含 Mermaid 代码块的 .md 文件，整体视为 Mermaid 语法（兼容纯流程图文件）。"""
        f = tmp_path / "plain.md"
        f.write_text("flowchart TD\n  A[节点A] --> B[节点B]\n", encoding="utf-8")
        chart = parse_file(str(f))
        labels = {n.label for n in chart.nodes}
        assert "节点A" in labels

    def test_pure_mermaid_file(self, tmp_path):
        """.mermaid 纯文件仍可正常解析。"""
        f = tmp_path / "flow.mermaid"
        f.write_text("flowchart TD\n  X[订单] --> Y[审批]\n", encoding="utf-8")
        chart = parse_file(str(f))
        assert any(n.label == "订单" for n in chart.nodes)

    def test_md_with_multiple_mermaid_blocks_uses_first(self, tmp_path):
        """含多个 mermaid 代码块时，应只解析第一个。"""
        f = tmp_path / "multi.md"
        f.write_text(
            "```mermaid\nflowchart TD\n  A[第一个块] --> B[节点B]\n```\n\n"
            "```mermaid\nflowchart TD\n  C[第二个块] --> D[节点D]\n```\n",
            encoding="utf-8",
        )
        chart = parse_file(str(f))
        labels = {n.label for n in chart.nodes}
        assert "第一个块" in labels
        assert "第二个块" not in labels
