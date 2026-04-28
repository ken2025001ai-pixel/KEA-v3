# tests/test_flowchart_checker.py
import pytest
from kea.parser.mermaid_parser import parse_mermaid
from kea.validator.flowchart_checker import FlowchartChecker, CheckIssue


def _check(mermaid_text: str) -> list[CheckIssue]:
    chart = parse_mermaid(mermaid_text)
    return FlowchartChecker().check(chart)


def test_s1_no_start_node():
    issues = _check("""
flowchart TD
  A[动作] --> B((结束))
""")
    checks = [i.check for i in issues]
    assert "S1" in checks


def test_s1_multiple_start_nodes():
    issues = _check("""
flowchart TD
  S1((开始)) --> A[动作]
  S2((开始)) --> B[动作]
  A --> E((结束))
  B --> E
""")
    checks = [i.check for i in issues]
    assert "S1" in checks


def test_s1_passes_with_one_start():
    issues = _check("""
flowchart TD
  S((开始)) --> A[动作] --> E((结束))
""")
    assert not any(i.check == "S1" for i in issues)


def test_s2_no_end_node():
    issues = _check("""
flowchart TD
  S((开始)) --> A[动作] --> B[动作2]
""")
    assert any(i.check == "S2" for i in issues)


def test_s2_passes_with_end():
    issues = _check("""
flowchart TD
  S((开始)) --> A[动作] --> E((结束))
""")
    assert not any(i.check == "S2" for i in issues)


def test_s3_decision_one_branch():
    issues = _check("""
flowchart TD
  S((开始)) --> D{条件?}
  D -->|是| A[动作]
  A --> E((结束))
""")
    assert any(i.check == "S3" for i in issues)


def test_s3_decision_two_branches():
    issues = _check("""
flowchart TD
  S((开始)) --> D{条件?}
  D -->|是| A[动作]
  D -->|否| B[其他]
  A --> E((结束))
  B --> E
""")
    assert not any(i.check == "S3" for i in issues)


def test_s4_isolated_node_no_input():
    issues = _check("""
flowchart TD
  S((开始)) --> A[动作] --> E((结束))
  B[孤立节点] --> E
""")
    assert any(i.check == "S4" and i.node_id == "B" for i in issues)


def test_s4_dead_node_no_output():
    issues = _check("""
flowchart TD
  S((开始)) --> A[动作]
  A --> B[死节点]
  A --> E((结束))
""")
    assert any(i.check == "S4" and i.node_id == "B" for i in issues)


def test_s4_start_allowed_no_input():
    """START 节点无入路是合法的."""
    issues = _check("""
flowchart TD
  S((开始)) --> A[动作] --> E((结束))
""")
    assert not any(i.check == "S4" and i.node_id == "S" for i in issues)


def test_s4_end_allowed_no_output():
    """END 节点无出路是合法的."""
    issues = _check("""
flowchart TD
  S((开始)) --> A[动作] --> E((结束))
""")
    assert not any(i.check == "S4" and i.node_id == "E" for i in issues)


def test_clean_flowchart_no_issues():
    """标准合规流程图无任何 issue."""
    issues = _check("""
flowchart TD
  S((开始)) --> D{条件?}
  D -->|是| A[动作A]
  D -->|否| B[动作B]
  A --> E((结束))
  B --> E
""")
    assert issues == []
