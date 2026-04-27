"""KEA AgentFile lint — 确定性结构校验，不依赖 LLM。

检查 Phase 文件和 Sub-skill 文件的合规性：
1. Phase: 门控完整性、kea 调用签名、错误处理
2. Sub-skill: SUBAGENT-STOP、契约格式、禁止交互
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# 已知的 kea CLI 命令签名
# ---------------------------------------------------------------------------

KEA_COMMANDS: dict[str, dict[str, Any]] = {
    "parse": {"args": ["target"], "flags": []},
    "mermaid": {"args": ["target"], "flags": []},
    "validate": {"args": ["target"], "flags": []},
    "trace": {"args": ["logic"], "flags": ["--scenarios", "--mock", "--count"]},
    "codegen": {"args": ["target"], "flags": ["-o", "--output"]},
    "status": {"args": ["target?"], "flags": []},
    "index": {"args": ["target?"], "flags": []},
    "impact": {"args": ["target"], "flags": ["--base-dir"]},
    "ingest": {
        "args": [],
        "flags": ["--source", "--source-dir", "--domain", "--domain-cn", "--output-dir"],
    },
}

# Phase gate 条件应使用的 valid category 字符串（来自 validator）
VALID_ISSUE_CATEGORIES = {
    "引用失效", "输入缺失", "输出缺失", "伪代码引用失效",
    "孤立动作", "字段不存在", "主键缺失", "结构缺失",
    "属性定义不完整", "触发条件缺失", "规则表达式缺失",
    "伪代码缺失", "调用违规", "回滚缺失", "ID缺失", "名称缺失",
    "agent_context 缺失", "输入参数定义不完整", "类型未知",
    "severity 无效", "伪代码语法", "伪代码结构",
}

# Phase 门控必须包含的关键词
GATE_REQUIRED_KEYWORDS = ["门控评估", "自动验证"]
ROLLBACK_REQUIRED_KEYWORDS = ["回退处理"]
SUBAGENT_STOP_MARKER = "<SUBAGENT-STOP>"


@dataclass
class LintIssue:
    file: str
    line: int
    severity: str  # error / warning
    message: str


@dataclass
class LintReport:
    issues: list[LintIssue] = field(default_factory=list)

    def error_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "error")

    def warning_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "warning")

    def to_dict(self) -> dict[str, Any]:
        return {
            "total": len(self.issues),
            "errors": self.error_count(),
            "warnings": self.warning_count(),
            "issues": [
                {"file": i.file, "line": i.line, "severity": i.severity, "message": i.message}
                for i in self.issues
            ],
        }


class AgentFileLinter:
    """AgentFile 编排层结构校验器."""

    def lint_directory(self, agentfile_dir: str) -> LintReport:
        report = LintReport()
        base = Path(agentfile_dir)

        phases_dir = base / "phases"
        skills_dir = base / "skills"

        if phases_dir.is_dir():
            for f in sorted(phases_dir.glob("phase-*.md")):
                report.issues.extend(self._lint_phase(f))

        if skills_dir.is_dir():
            for skill_dir in sorted(skills_dir.iterdir()):
                if skill_dir.is_dir():
                    skill_file = skill_dir / "SKILL.md"
                    if skill_file.is_file():
                        report.issues.extend(self._lint_sub_skill(skill_file))

        return report

    # ------------------------------------------------------------------
    # Phase 校验
    # ------------------------------------------------------------------

    def _lint_phase(self, path: Path) -> list[LintIssue]:
        issues: list[LintIssue] = []
        content = path.read_text(encoding="utf-8")
        lines = content.split("\n")
        filename = str(path.name)

        # 1. 门控节存在
        if not any("门控评估" in line for line in lines):
            issues.append(LintIssue(filename, 0, "error", "缺少「门控评估」节"))

        # 2. 回退处理节存在
        if not any("回退处理" in line for line in lines):
            issues.append(LintIssue(filename, 0, "warning", "缺少「回退处理」节"))

        # 3. kea 调用签名检查
        for i, line in enumerate(lines):
            if "python3 -m kea" in line:
                issues.extend(self._check_kea_call(filename, i + 1, line))

        # 4. gate category 字符串有效性
        for i, line in enumerate(lines):
            issues.extend(self._check_gate_category(filename, i + 1, line))

        return issues

    # ------------------------------------------------------------------
    # Sub-skill 校验
    # ------------------------------------------------------------------

    def _lint_sub_skill(self, path: Path) -> list[LintIssue]:
        issues: list[LintIssue] = []
        content = path.read_text(encoding="utf-8")
        filename = f"skills/{path.parent.name}/SKILL.md"

        # 1. SUBAGENT-STOP 标记
        if SUBAGENT_STOP_MARKER not in content:
            issues.append(LintIssue(filename, 0, "error", "缺少 <SUBAGENT-STOP> 标记"))

        # 2. 禁止用户交互（非 interview 类型）。
        if "interview" not in str(path.parent.name):
            # 移除否定式声明（"不与用户交互"、"Do NOT ask..." 等）
            cleaned = content
            cleaned = re.sub(r'不与用户[交互对话].*', '', cleaned)
            cleaned = re.sub(r'[Dd]o\s+NOT\s+ask\s+any\s+questions\s+or\s+interact\s+with\s+the\s+user.*', '', cleaned)
            cleaned = re.sub(r'[Dd]o\s+NOT\s+interact\s+with\s+the\s+user.*', '', cleaned)
            if any(kw in cleaned for kw in ["与用户对话", "与用户交互", "ask the user to", "interact with the user"]):
                issues.append(LintIssue(filename, 0, "error", "非 interview sub-skill 包含用户交互指令"))

        # 3. kea parse 自检调用
        if "extract-" in str(path.parent.name):
            if "kea parse" not in content and "kea --format json parse" not in content:
                issues.append(LintIssue(filename, 0, "warning", "extract sub-skill 缺少 kea parse 自检步骤"))

        # 4. kea 调用签名检查
        lines = content.split("\n")
        for i, line in enumerate(lines):
            if "python3 -m kea" in line:
                issues.extend(self._check_kea_call(filename, i + 1, line))

        return issues

    # ------------------------------------------------------------------
    # kea 命令签名检查
    # ------------------------------------------------------------------

    def _check_kea_call(self, filename: str, lineno: int, line: str) -> list[LintIssue]:
        issues: list[LintIssue] = []

        # 提取命令名
        cmd_match = re.search(r'python3 -m kea\s+(?:--format\s+\w+\s+)?(\w+)', line)
        if not cmd_match:
            return issues

        cmd_name = cmd_match.group(1)
        if cmd_name not in KEA_COMMANDS:
            issues.append(LintIssue(filename, lineno, "error", f"未知 kea 命令: {cmd_name}"))
            return issues

        cmd_spec = KEA_COMMANDS[cmd_name]

        # 检查 --format json 位置（必须在子命令之前）
        if "--format json" in line or "--format human" in line:
            fmt_pos = line.find("--format")
            cmd_pos = line.find(cmd_name)
            if fmt_pos > cmd_pos:
                issues.append(LintIssue(
                    filename, lineno, "error",
                    f"--format json 必须放在子命令之前: python3 -m kea --format json {cmd_name} ...",
                ))

        # 检查未知 flag（排除变量模板如 {OBJECTS_DIR}）
        flag_matches = re.findall(r'(--[\w-]+)', line)
        for flag in flag_matches:
            if flag not in cmd_spec["flags"] and flag != "--format":
                # 检查是不是变量模板占位符 {VAR}
                if not re.match(r'--\{[A-Z_]+\}', flag):
                    issues.append(LintIssue(
                        filename, lineno, "warning",
                        f"kea {cmd_name} 不支持 flag: {flag}",
                    ))

        return issues

    # ------------------------------------------------------------------
    # Gate category 字符串检查
    # ------------------------------------------------------------------

    def _check_gate_category(self, filename: str, lineno: int, line: str) -> list[LintIssue]:
        issues: list[LintIssue] = []

        # 匹配 category=`xxx` 或 category 为 xxx。处理 A/B 格式（两个类别用 / 分隔）
        cat_match = re.findall(r'category[=`]\s*`?([^`\s,;]+(?:`?/`?[^`\s,;]+)?)', line)
        for cat_raw in cat_match:
            # 拆分 A/B 格式
            for cat in re.split(r'`?/`?', cat_raw):
                cat = cat.strip('`\'" ')
                if cat and cat not in VALID_ISSUE_CATEGORIES:
                    # 排除变量引用如 {category_field}
                    if not cat.startswith("{"):
                        issues.append(LintIssue(
                            filename, lineno, "error",
                            f"无效的 issue category: '{cat}'（validator 不会发出此字符串）",
                        ))

        return issues
