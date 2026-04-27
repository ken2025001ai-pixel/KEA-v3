---
date: 2026-04-27
status: completed
audit_scope:
  - AgentFile/SKILL.md
  - AgentFile/phases/ (12 files)
  - AgentFile/skills/ (10 files)
  - AgentFile/templates/ (6 files)
  - AgentFile/CLAUDE.md
---

# KEA-v3 AgentFile 编排层全面审计

## 审计方法

3 个并行 Agent 分别审计 Phase 1-5、Phase 6-12、Sub-skills+Templates，按 6 个维度（路由正确性、门控一致性、工具调用完备、契约清晰性、错误处理、模板合规）逐文件检查。

## 发现摘要

### Critical（已修复，7 项）

1. **`--format json` 位置错误**：所有 Phase 和 Sub-skill 文件中 `--format json` 放在子命令之后。kea CLI 要求 `python3 -m kea --format json <cmd>`。影响 Phase 1/3/4/5/6/7/8/9/11 + 6 个 Sub-skill。

2. **Phase 12 `kea trace` CLI 完全错误**：使用了不存在的 `--objects`/`--logic`/`--actions`/`--rules`/`--scenario` 标志。实际签名：`kea trace LOGIC [--scenarios] [--mock] [--count]`。

3. **Phase 12 标题错误**："第 10 阶段" → "第 12 阶段"。回退路径文本与表格不一致。

4. **Phase 6 门控条件 ③④⑤⑥ 无执行步骤**：Gate 表描述了检查方法但无对应实现。修复方案：③④⑥ 改用 `kea validate` 输出（validate 已覆盖死链/输入输出/子流程引用检查），⑤ 保留手工分支检查。

5. **Phase 7 门控条件 ③⑤ 无执行步骤**：修复方案：改用 `kea validate` 输出（validate 已覆盖孤立动作和输入输出检查）。

6. **Phase 8 门控条件 ①② 无执行步骤**：修复方案：改用 `kea validate` 输出（validate R-RULE-002 已覆盖目标存在性和字段有效性）。

7. **4 个核心模板与 extract sub-skill 输出不匹配**：object/logic/action/rule 模板定义的 YAML 字段（agent_context、状态机、伪代码等）与 sub-skill 实际输出完全不同。模板已重写为匹配 sub-skill 实际输出格式。

### Subagent 契约（已修复，4 项）

8. **Phase 2 不检查 interview 返回状态**：新增 Step 2.5 验证访谈摘要文件是否存在。

9. **Phase 4 只处理 BLOCKED/NEEDS_CONTEXT**：新增 DONE（空数组）和 DONE_WITH_CONCERNS（非空数组）处理。

10. **Phase 5/6/7 coverage-check dispatch 无状态分支**：新增覆盖率报告有效性检查和异常处理。

11. **契约分型**：AgentFile/CLAUDE.md 新增"Sub-skill 契约分型"章节，识别三种交互模式（生成型/分析型/交互型），各自定义返回格式和 Phase 处理责任。

### 已知问题（待后续处理）

- **kea validate R-RULE-002 检查 `applies_to`，但 extract-rules 输出使用 `relations`**：validator 与 extract sub-skill 输出格式存在字段名不匹配。当前 Phase 8 gate 通过 `引用失效` 和 `字段不存在` category 间接检查，可能有漏检。需要后续对齐 validator 或 sub-skill 的字段名。
- **Phase 5 覆盖率失败回退无量化阈值**：依赖 LLM 主观判断"领域边界偏差"vs"候选数不准"，建议添加数值阈值。
- **kea CLI 自身 epilog 示例中 `--format json` 也在子命令之后**（cli.py:631-636），但实际 argparse 不接受这个位置。需要修复 CLI 的 epilog 或调整 argparse 参数位置。

## 架构决策

### 设计原则（已录入 CLAUDE.md 和 AgentFile/CLAUDE.md）

- **原则一：Skill 为主，工具为辅** — 能用 kea 工具验证的必须调用工具，不允许 LLM 猜测或手工 grep 模拟
- **原则二：追求确定性，人类专家舒适高效** — 自动验证在前，人类确认在后。疑虑前置，每次交互有获得感

### Sub-skill 契约分型

承认三种不同性质的子任务各有不同的交互模式，不再强制统一 4 状态码：

| 类型 | 返回格式 | 代表 |
|------|---------|------|
| 生成型 | DONE / DONE_WITH_CONCERNS / NEEDS_CONTEXT / BLOCKED | extract-* |
| 分析型 | `{status, issues[], confidence}` JSON | flowchart-validate, semantic-check, coverage-check |
| 交互型 | 文件存在性验证 | interview |

### 调用层级（修正）

```
Phase → kea CLI（确定性校验，Phase 直接调用）
Phase → Sub-skill（LLM 推理，Dispatch 为 subagent）
```

不再有"Sub-skill → kea"的三级链。Sub-skill 只做 LLM 推理，Phase 负责所有工具调用。

## 变更文件清单

| 文件 | 变更类型 |
|------|---------|
| AgentFile/SKILL.md | 架构图修正 |
| AgentFile/CLAUDE.md | 新增设计原则 + 契约分型 |
| phases/phase-1-research.md | `--format json` 位置 |
| phases/phase-2-interview.md | 新增 Step 2.5 验证访谈输出 |
| phases/phase-3-flowchart-generate.md | `--format json` 位置 |
| phases/phase-4-flowchart-validate.md | `--format json` + 返回状态处理 |
| phases/phase-5-extract-objects.md | `--format json` + kea validate + coverage status |
| phases/phase-6-extract-logic.md | `--format json` + kea validate 输出映射 + coverage status |
| phases/phase-7-extract-actions.md | `--format json` + kea validate 输出映射 + coverage status |
| phases/phase-8-extract-rules.md | `--format json` + kea validate 输出映射 |
| phases/phase-9-rule-check.md | `--format json` ×4 |
| phases/phase-11-coverage-check.md | `--format json` + kea status |
| phases/phase-12-scenario-trace.md | CLI 重写 + 标题 + 回退文本 |
| skills/extract-*/SKILL.md (4) | `--format json` + kea parse 自检 |
| skills/semantic-check/SKILL.md | `--format json` + Step 0 kea parse |
| skills/coverage-check/SKILL.md | `--format json` + Step 0 kea parse |
| templates/object-template.md | 重写匹配 extract-objects 输出 |
| templates/logic-template.md | 重写匹配 extract-logic 输出 |
| templates/action-template.md | 重写匹配 extract-actions 输出 |
| templates/rule-template.md | 重写匹配 extract-rules 输出 |
| CLAUDE.md | 新增核心设计原则 |
