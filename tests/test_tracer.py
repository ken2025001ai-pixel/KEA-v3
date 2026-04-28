"""Tracer 单元测试 — PseudocodeExecutor."""
import pytest
from kea.parser.document_parser import DocumentParser
from kea.tracer.pseudocode_executor import PseudocodeExecutor
from kea.tracer.scenario_generator import Scenario


def _make_doc(pseudocode: str) -> "KnowledgeDocument":
    raw = f"""---
type: logic
id: test
name: 测试
domain: test
agent_context:
  one_liner: test
---
# 业务描述
test

## 逻辑描述
```pseudo
{pseudocode}
```
"""
    return DocumentParser().parse_text(raw)


class TestPseudocodeExecutor:
    def test_execute_function_main(self):
        """function main 包装的伪代码应正常执行."""
        doc = _make_doc("""function main(order_id: str) -> dict:
    assert order_id != '', 'order_id required'
    result = 42
    call_action('check_order')
    return {'success': True}

function rollback(ctx):
    // cleanup
""")
        scenario = Scenario(name="test", inputs={"order_id": "ORD-001"})
        executor = PseudocodeExecutor()
        trace = executor.execute(doc, scenario)
        assert trace.reached_end
        assert len(trace.steps) >= 3

    def test_assert_failure(self):
        """assert 失败应记录 issue 并停止."""
        doc = _make_doc("""function main(x: int) -> dict:
    assert x > 10, 'x too small'
    return {'ok': True}
""")
        scenario = Scenario(name="test", inputs={"x": 5})
        executor = PseudocodeExecutor()
        trace = executor.execute(doc, scenario)
        assert any("x too small" in issue for issue in trace.issues)

    def test_call_action_recorded(self):
        """call_action 应被记录到 state 中."""
        doc = _make_doc("""function main() -> dict:
    call_action('deduct_inventory')
    call_action('send_notification')
    return {'ok': True}
""")
        scenario = Scenario(name="test", inputs={})
        executor = PseudocodeExecutor()
        trace = executor.execute(doc, scenario)
        assert "__call_deduct_inventory__" in executor.state
        assert "__call_send_notification__" in executor.state

    def test_if_else_branch(self):
        """if/else 分支应正确选择路径."""
        doc = _make_doc("""function main(flag: bool) -> dict:
    result = 'default'
    if flag:
        result = 'true_path'
    else:
        result = 'false_path'
    return {'path': result}
""")
        # True branch
        scenario_t = Scenario(name="test", inputs={"flag": True})
        executor_t = PseudocodeExecutor()
        trace_t = executor_t.execute(doc, scenario_t)
        assert executor_t.state.get("result") == "true_path"

        # False branch
        scenario_f = Scenario(name="test", inputs={"flag": False})
        executor_f = PseudocodeExecutor()
        trace_f = executor_f.execute(doc, scenario_f)
        assert executor_f.state.get("result") == "false_path"

    def test_empty_pseudocode(self):
        """空伪代码不应 crash."""
        doc = _make_doc("")
        scenario = Scenario(name="test", inputs={})
        executor = PseudocodeExecutor()
        trace = executor.execute(doc, scenario)
        assert "伪代码为空" in trace.issues[0]

    def test_skip_non_main_function(self):
        """非 main 函数应被跳过，不含在 steps 中."""
        doc = _make_doc("""function main() -> dict:
    result = 1
    return {'ok': True}

function helper():
    result = 999
""")
        scenario = Scenario(name="test", inputs={})
        executor = PseudocodeExecutor()
        trace = executor.execute(doc, scenario)
        # helper() 不应被执行，result 应保持 main 设置的值
        assert executor.state.get("result") == 1

    def test_for_loop_execution(self):
        """for 循环应遍历列表."""
        doc = _make_doc("""function main() -> dict:
    total = 0
    for item in [1, 2, 3]:
        total = total + item
    return {'total': total}
""")
        scenario = Scenario(name="test", inputs={})
        executor = PseudocodeExecutor()
        trace = executor.execute(doc, scenario)
        assert executor.state.get("total") == 6
