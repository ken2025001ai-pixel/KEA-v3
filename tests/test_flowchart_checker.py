# tests/test_flowchart_checker.py
import subprocess, json as _json
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


def test_cli_json_output_clean(tmp_path):
    """CLI 输出合规流程图时 summary.failed == 0."""
    md = tmp_path / "流程.md"
    md.write_text("""---
domain: test
process: 流程
phase: flowchart
created_at: 2026-04-28
---
```mermaid
flowchart TD
  S((开始)) --> D{条件?}
  D -->|是| A[动作A]
  D -->|否| B[动作B]
  A --> E((结束))
  B --> E
```
""")
    result = subprocess.run(
        ["python3", "-m", "kea", "--format", "json", "flowchart-check", str(tmp_path)],
        capture_output=True, text=True,
        cwd="/Users/kenkangning/KEA-v3"
    )
    data = _json.loads(result.stdout)
    assert data["summary"]["failed"] == 0
    assert data["results"][0]["passed"] is True


def test_cli_json_output_with_issue(tmp_path):
    """CLI 输出含问题流程图时 summary.failed == 1，issues 非空。"""
    md = tmp_path / "有问题.md"
    md.write_text("""---
domain: test
process: 有问题
phase: flowchart
created_at: 2026-04-28
---
```mermaid
flowchart TD
  A[动作] --> E((结束))
```
""")
    result = subprocess.run(
        ["python3", "-m", "kea", "--format", "json", "flowchart-check", str(tmp_path)],
        capture_output=True, text=True,
        cwd="/Users/kenkangning/KEA-v3"
    )
    data = _json.loads(result.stdout)
    assert data["summary"]["failed"] == 1
    checks = [i["check"] for i in data["results"][0]["issues"]]
    assert "S1" in checks
