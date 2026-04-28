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
