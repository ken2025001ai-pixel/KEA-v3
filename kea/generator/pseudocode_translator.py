"""伪代码到 Python 的翻译器.

将知识文档中的伪代码（```pseudo 代码块）翻译为可执行的 Python 代码。

翻译规则：
- function name(params) -> type:  →  def name(params) -> type:
- assert condition, "message"      →  assert condition, "message"
- call_action("id", {...})         →  self.registry.call("id", {...})
- 查询X(y)                         →  self.dao.x.get(y)
- if/elif/else                     →  if/elif/else
- for 变量 in 可迭代:              →  for 变量 in 可迭代:
- return {...}                     →  return {...}
- // 注释                          →  # 注释
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


class PseudocodeTranslator:
    """伪代码翻译器."""

    # 数据访问层映射表（可配置）
    DAO_MAPPING: dict[str, str] = {
        "订单": "order",
        "库存": "inventory",
        "用户": "user",
        "SKU": "sku",
        "商品": "product",
    }

    def translate(self, pseudocode: str, doc_id: str = "") -> str:
        """将伪代码翻译为 Python.

        Args:
            pseudocode: 伪代码文本
            doc_id: 文档 ID，用于生成类名

        Returns:
            Python 代码字符串
        """
        lines = pseudocode.split("\n")
        result_lines = []
        indent_stack = [0]  # 缩进层级栈

        for raw_line in lines:
            line = raw_line.rstrip()
            if not line:
                result_lines.append("")
                continue

            # 计算当前缩进
            current_indent = len(line) - len(line.lstrip())
            stripped = line.strip()

            # 处理缩进层级变化
            while current_indent < indent_stack[-1]:
                indent_stack.pop()
            if current_indent > indent_stack[-1]:
                indent_stack.append(current_indent)

            translated = self._translate_line(stripped)
            if translated:
                result_lines.append("    " * (len(indent_stack) - 1) + translated)

        return "\n".join(result_lines)

    def _translate_line(self, line: str) -> str:
        """翻译单行伪代码."""

        # 1. 函数定义
        # function name(params) -> type:
        func_match = re.match(
            r'function\s+(\w+)\s*\((.*?)\)\s*(?:->\s*(\w+))?:',
            line
        )
        if func_match:
            name, params, ret_type = func_match.groups()
            py_params = self._translate_params(params)
            py_ret = f" -> {self._map_type(ret_type)}" if ret_type else ""
            return f"def {name}({py_params}){py_ret}:"

        # 2. assert 语句
        assert_match = re.match(r'assert\s+(.+)', line)
        if assert_match:
            condition = assert_match.group(1).strip()
            return f"assert {self._translate_expr(condition)}"

        # 3. call_action
        call_match = re.match(
            r'call_action\s*\(\s*["\']([^"\']+)["\']\s*,\s*\{(.*?)\}\s*\)',
            line
        )
        if call_match:
            action_id, args = call_match.groups()
            return f"self.registry.call('{action_id}', {{{self._translate_expr(args)}}})"

        # 4. 数据查询：查询X(y) → self.dao.x.get(y)
        query_match = re.match(r'查询(\w+)\s*\((.*?)\)', line)
        if query_match:
            entity, args = query_match.groups()
            dao_name = self.DAO_MAPPING.get(entity, entity.lower())
            return f"self.dao.{dao_name}.get({self._translate_expr(args)})"

        # 5. if/elif/else
        if line.startswith("if "):
            condition = line[3:].rstrip(":")
            return f"if {self._translate_expr(condition)}:"
        if line.startswith("elif "):
            condition = line[5:].rstrip(":")
            return f"elif {self._translate_expr(condition)}:"
        if line == "else:" or line == "else":
            return "else:"

        # 6. for 循环
        for_match = re.match(r'for\s+(\w+)\s+in\s+(.+?):', line)
        if for_match:
            var, iterable = for_match.groups()
            return f"for {var} in {self._translate_expr(iterable)}:"

        # 7. return
        if line.startswith("return "):
            expr = line[7:]
            return f"return {self._translate_expr(expr)}"
        if line == "return":
            return "return"

        # 8. 变量赋值
        assign_match = re.match(r'(\w+)\s*=\s*(.+)', line)
        if assign_match:
            var, expr = assign_match.groups()
            return f"{var} = {self._translate_expr(expr)}"

        # 9. 方法调用（非查询）
        method_match = re.match(r'(\w+)\s*\((.*?)\)', line)
        if method_match:
            name, args = method_match.groups()
            return f"self._{name}({self._translate_expr(args)})"

        # 10. 注释 //
        if line.startswith("//"):
            return f"# {line[2:].strip()}"

        # 11. 其他 —— 直接翻译表达式
        return self._translate_expr(line)

    def _translate_params(self, params: str) -> str:
        """翻译函数参数列表."""
        if not params.strip():
            return ""
        parts = [p.strip() for p in params.split(",")]
        result = []
        for part in parts:
            # 格式: name: type
            if ":" in part:
                name, type_ = part.split(":", 1)
                py_type = self._map_type(type_.strip())
                result.append(f"{name.strip()}: {py_type}")
            else:
                result.append(part)
        return ", ".join(result)

    def _translate_expr(self, expr: str) -> str:
        """翻译表达式中的中文标识符和特殊语法."""
        expr = expr.strip()

        # 替换中文比较运算符
        expr = expr.replace(">=", ">=")
        expr = expr.replace("<=", "<=")
        expr = expr.replace("==", "==")

        # 翻译查询操作：查询X(y) → self.dao.x.get(y)
        expr = re.sub(
            r'查询(\w+)\s*\((.*?)\)',
            lambda m: f"self.dao.{self.DAO_MAPPING.get(m.group(1), m.group(1).lower())}.get({self._translate_expr(m.group(2))})",
            expr
        )

        return expr

    def _map_type(self, type_str: str | None) -> str:
        """将伪代码类型映射到 Python 类型."""
        if not type_str:
            return "Any"

        type_map = {
            "string": "str",
            "字符串": "str",
            "int": "int",
            "integer": "int",
            "整数": "int",
            "float": "float",
            "number": "float",
            "数值": "float",
            "金额": "Decimal",
            "bool": "bool",
            "boolean": "bool",
            "布尔": "bool",
            "array": "list",
            "列表": "list",
            "object": "dict",
            "对象": "dict",
        }

        return type_map.get(type_str.strip().lower(), type_str)


# ============================================================================
# 便捷函数
# ============================================================================

def translate_pseudocode(pseudocode: str, doc_id: str = "") -> str:
    """便捷函数：翻译伪代码."""
    return PseudocodeTranslator().translate(pseudocode, doc_id)
