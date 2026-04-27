"""伪代码执行器 — 模拟执行伪代码，追踪状态变化.

这是一个简化版的 AST 解释器，用于在不实际运行 Python 代码的情况下，
验证伪代码的逻辑正确性。它维护一个虚拟的状态空间，按步骤执行伪代码。

限制：
- 不支持真正的函数调用（call_action 只记录，不执行）
- 不支持外部数据查询（查询X 返回模拟值）
- 只支持基本类型（str/int/float/bool/list/dict）
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from kea.parser.models import KnowledgeDocument
from kea.tracer.scenario_generator import Scenario


@dataclass
class ExecutionStep:
    """执行步骤记录."""

    step_num: int = 0
    line: str = ""
    state_before: dict[str, Any] = field(default_factory=dict)
    state_after: dict[str, Any] = field(default_factory=dict)
    result: str = ""           # pass / fail / skip
    issue: str = ""            # 发现的问题


@dataclass
class ExecutionTrace:
    """执行追踪结果."""

    scenario_name: str = ""
    steps: list[ExecutionStep] = field(default_factory=list)
    final_state: dict[str, Any] = field(default_factory=dict)
    issues: list[str] = field(default_factory=list)
    reached_end: bool = False


class PseudocodeExecutor:
    """伪代码执行器."""

    def __init__(self, mock_data: dict[str, Any] | None = None) -> None:
        self.state: dict[str, Any] = {}
        self.mock_data = mock_data or {}
        self.steps: list[ExecutionStep] = []
        self.step_counter = 0

    def execute(self, doc: KnowledgeDocument, scenario: Scenario) -> ExecutionTrace:
        """在指定场景下执行文档的伪代码.

        Args:
            doc: 知识文档（Action 或 Logic）
            scenario: 测试场景

        Returns:
            执行追踪结果
        """
        trace = ExecutionTrace(scenario_name=scenario.name)
        self.state = dict(scenario.inputs)
        self.steps = []
        self.step_counter = 0

        code = doc.pseudocode
        if not code:
            trace.issues.append("伪代码为空，无法执行")
            return trace

        # 按行解析伪代码
        lines = self._parse_lines(code)

        # 执行主函数体
        try:
            self._execute_block(lines, trace)
            trace.reached_end = True
        except ExecutionError as e:
            trace.issues.append(str(e))
        except Exception as e:
            trace.issues.append(f"执行异常: {e}")

        trace.steps = self.steps
        trace.final_state = dict(self.state)
        return trace

    def _parse_lines(self, code: str) -> list[tuple[int, str]]:
        """解析伪代码为带缩进的行列表."""
        lines = []
        for raw_line in code.split("\n"):
            line = raw_line.rstrip()
            if not line or line.strip().startswith("//"):
                continue
            indent = len(line) - len(line.lstrip())
            lines.append((indent, line.strip()))
        return lines

    def _execute_block(self, lines: list[tuple[int, str]], trace: ExecutionTrace, start_idx: int = 0, base_indent: int = 0) -> int:
        """执行一个代码块，返回下一个要执行的行索引.

        Returns:
            下一个要处理的行索引（超出范围为正常结束）
        """
        i = start_idx
        while i < len(lines):
            indent, line = lines[i]

            # 缩进回退表示块结束
            if indent < base_indent and base_indent > 0:
                return i

            # 跳过空行和注释
            if not line or line.startswith("//"):
                i += 1
                continue

            # 执行单行
            result = self._execute_line(line, trace)

            if result == "return":
                return len(lines)  # 函数返回
            elif result == "continue":
                i += 1
                continue
            elif result == "break":
                return i + 1

            # 处理块语句（if/for/function）
            if line.startswith("if ") or line.startswith("elif ") or line == "else:":
                # 找到 if/elif/else 对应的块
                block_end = self._find_block_end(lines, i + 1, indent)
                block_lines = lines[i + 1:block_end]

                if line.startswith("if ") or line.startswith("elif "):
                    condition = line[line.find(" ") + 1:].rstrip(":")
                    if self._eval_condition(condition):
                        i = self._execute_block(block_lines, trace, 0, indent)
                        if i < len(lines) and lines[i][1].startswith("elif "):
                            # 跳过剩余的 elif/else
                            i = self._skip_else_block(lines, i, indent)
                        continue
                    else:
                        i = block_end
                        continue
                elif line == "else:":
                    i = self._execute_block(block_lines, trace, 0, indent)
                    continue

            elif line.startswith("for "):
                # for 循环
                loop_end = self._find_block_end(lines, i + 1, indent)
                block_lines = lines[i + 1:loop_end]

                # 解析循环变量和可迭代对象
                match = re.match(r'for\s+(\w+)\s+in\s+(.+):', line)
                if match:
                    var, iterable_expr = match.groups()
                    iterable = self._eval_expr(iterable_expr)
                    if isinstance(iterable, (list, tuple)):
                        for item in iterable:
                            self.state[var] = item
                            self._execute_block(list(block_lines), trace, 0, indent)
                    else:
                        trace.issues.append(f"for 循环的可迭代对象不是列表: {iterable_expr}")
                i = loop_end
                continue

            elif line.startswith("function "):
                # 函数定义 — main 执行其体，其他函数跳过
                func_name = line[9:].split("(")[0].strip()
                if func_name == "main":
                    func_end = self._find_block_end(lines, i + 1, indent)
                    block_lines = lines[i + 1:func_end]
                    self._execute_block(block_lines, trace, 0, indent)
                    i = func_end
                else:
                    func_end = self._find_block_end(lines, i + 1, indent)
                    i = func_end
                continue

            i += 1

        return len(lines)

    def _execute_line(self, line: str, trace: ExecutionTrace) -> str:
        """执行单行代码.

        Returns:
            "continue" / "return" / "break" / ""
        """
        self.step_counter += 1
        step = ExecutionStep(
            step_num=self.step_counter,
            line=line,
            state_before=dict(self.state),
        )

        try:
            # assert
            if line.startswith("assert "):
                expr = line[7:]
                # 提取条件和消息
                if "," in expr:
                    condition, msg = expr.split(",", 1)
                    msg = msg.strip().strip('"').strip("'")
                else:
                    condition = expr
                    msg = "Assertion failed"

                if not self._eval_condition(condition.strip()):
                    step.result = "fail"
                    step.issue = f"assert 失败: {msg}"
                    self.steps.append(step)
                    raise ExecutionError(f"Assert failed: {msg}")

            # return
            elif line.startswith("return "):
                expr = line[7:]
                self.state["__return__"] = self._eval_expr(expr)
                step.result = "pass"
                step.state_after = dict(self.state)
                self.steps.append(step)
                return "return"

            elif line == "return":
                step.result = "pass"
                self.steps.append(step)
                return "return"

            # call_action
            elif "call_action" in line:
                # 记录调用，不实际执行。支持 call_action("id") 和 call_action("id", {...})
                match = re.search(r'call_action\s*\(\s*["\']([^"\']+)["\']', line)
                if match:
                    action_id = match.group(1)
                    self.state[f"__call_{action_id}__"] = True

            # 变量赋值
            elif "=" in line and not line.startswith("if") and not line.startswith("for"):
                self._execute_assignment(line)

            step.result = "pass"

        except ExecutionError:
            raise
        except Exception as e:
            step.result = "fail"
            step.issue = str(e)

        step.state_after = dict(self.state)
        self.steps.append(step)
        return ""

    def _execute_assignment(self, line: str) -> None:
        """执行赋值语句."""
        # 找到第一个 =（不是 == 或 >= 或 <=）
        for i, ch in enumerate(line):
            if ch == "=" and i > 0 and line[i - 1] not in "=<>!":
                var = line[:i].strip()
                expr = line[i + 1:].strip()
                self.state[var] = self._eval_expr(expr)
                return

    def _eval_condition(self, condition: str) -> bool:
        """评估条件表达式."""
        # 替换状态变量
        expr = self._substitute_vars(condition)
        try:
            return bool(eval(expr, {"__builtins__": {}}, {}))
        except Exception:
            # 无法评估时返回 True（不阻断）
            return True

    def _eval_expr(self, expr: str) -> Any:
        """评估表达式."""
        expr = expr.strip()

        # 字符串字面量
        if (expr.startswith('"') and expr.endswith('"')) or \
           (expr.startswith("'") and expr.endswith("'")):
            return expr[1:-1]

        # 查询操作
        query_match = re.match(r'查询(\w+)\s*\((.*?)\)', expr)
        if query_match:
            entity, args = query_match.groups()
            return self._mock_query(entity, args)

        # 字典字面量
        if expr.startswith("{") and expr.endswith("}"):
            try:
                return eval(expr, {"__builtins__": {}}, {})
            except Exception:
                return {}

        # 列表字面量
        if expr.startswith("[") and expr.endswith("]"):
            try:
                return eval(expr, {"__builtins__": {}}, {})
            except Exception:
                return []

        # 数值
        try:
            if "." in expr:
                return float(expr)
            return int(expr)
        except ValueError:
            pass

        # 布尔值
        if expr.lower() == "true":
            return True
        if expr.lower() == "false":
            return False

        # 变量引用
        substituted = self._substitute_vars(expr)
        try:
            return eval(substituted, {"__builtins__": {}}, {})
        except Exception:
            return substituted

    def _substitute_vars(self, expr: str) -> str:
        """将表达式中的变量替换为状态值."""
        result = expr
        # 按长度降序替换，避免短名覆盖长名
        for var in sorted(self.state.keys(), key=len, reverse=True):
            if var.startswith("__"):
                continue
            val = self.state[var]
            if isinstance(val, str):
                result = result.replace(var, f'"{val}"')
            elif isinstance(val, bool):
                result = result.replace(var, str(val))
            elif val is None:
                result = result.replace(var, "None")
            else:
                result = result.replace(var, str(val))
        return result

    def _mock_query(self, entity: str, args: str) -> Any:
        """模拟数据查询."""
        key = f"{entity}.{args}"
        if key in self.mock_data:
            return self.mock_data[key]
        # 返回默认值
        return {"status": "mock", "entity": entity}

    def _find_block_end(self, lines: list[tuple[int, str]], start: int, base_indent: int) -> int:
        """找到代码块的结束位置."""
        for i in range(start, len(lines)):
            indent, _ = lines[i]
            if indent <= base_indent:
                return i
        return len(lines)

    def _skip_else_block(self, lines: list[tuple[int, str]], start: int, base_indent: int) -> int:
        """跳过 else/elif 块."""
        i = start
        while i < len(lines):
            indent, line = lines[i]
            if indent < base_indent:
                return i
            if indent == base_indent and (line.startswith("elif ") or line == "else:"):
                block_end = self._find_block_end(lines, i + 1, indent)
                i = block_end
            else:
                i += 1
        return i


class ExecutionError(Exception):
    """执行错误."""

    pass
