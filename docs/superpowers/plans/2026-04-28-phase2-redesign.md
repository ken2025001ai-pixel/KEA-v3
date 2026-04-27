# Phase 2 重设计实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 Phase 2 从"全量访谈"重构为"评估驱动的定向补充"——Agent 先审报告质量，专家评审建议，按需定向补充。

**Architecture:** 新增 `evaluate-research` 分析型 sub-skill 负责 5 维度评估；`interview/SKILL.md` 精简为定向补充状态机；`phase-2-interview.md` 重写编排逻辑，串联两个 sub-skill；Phase 3 新增可选输入 `SUPPLEMENT_PATH`。

**Tech Stack:** Markdown + YAML frontmatter（AgentFile Skill 格式）；无代码变更，仅 Skill 文件编写。

---

## 文件变更清单

| 操作 | 文件路径 | 说明 |
|------|---------|------|
| 新增 | `AgentFile/skills/evaluate-research/SKILL.md` | 分析型 sub-skill，5 维度评估，输出结构化 JSON |
| 重写 | `AgentFile/skills/interview/SKILL.md` | 移除全量状态机，新增 GAP_ELICITATION / OPEN_FLOOR |
| 重写 | `AgentFile/phases/phase-2-interview.md` | 新编排：evaluate → 专家逐条确认 → 按需 interview |
| 小改 | `AgentFile/phases/phase-3-flowchart-generate.md` | 输入参数新增可选 `SUPPLEMENT_PATH` |
| 小改 | `AgentFile/SKILL.md` | 传参列表新增 `SUPPLEMENT_PATH` |

---

## Task 1: 新增 evaluate-research sub-skill

**Files:**
- Create: `AgentFile/skills/evaluate-research/SKILL.md`

- [ ] **Step 1: 创建目录并写入 SKILL.md**

文件内容：

```markdown
<SUBAGENT-STOP>
本文件作为 subagent 执行。若你是主 session Claude，请通过 Agent 工具 Dispatch 本 skill，而非直接读取执行。
</SUBAGENT-STOP>

# evaluate-research — 调研报告质量评估

你是一个分析型 subagent。读取调研报告，从 5 个维度评估质量，输出结构化 JSON 问题清单。**不与用户交互，不修改任何文件。**

## 输入参数（由 phase-2 在 Dispatch 时传入）

- `RESEARCH_REPORT_PATH`：调研报告文件路径
- `DOMAIN_CN` / `DOMAIN_EN`：领域信息

## 执行步骤

### Step 1: 读取报告

使用 Read 工具读取 `RESEARCH_REPORT_PATH` 的完整内容。

若文件不存在，直接返回：
```
状态：NEEDS_CONTEXT
缺少信息：RESEARCH_REPORT_PATH 文件不存在：{路径}
```

### Step 2: 五维度评估

逐维度分析，每个维度产出 0 至多条 issue：

**维度 1 — 覆盖度**
基于 `DOMAIN_CN` 的领域语义，判断报告中是否缺少该领域通常应有的核心概念（对象/逻辑/动作）。
- 仅标注"明显缺失"，不要过度发散
- 示例：采购领域缺少"入库单"对象候选

**维度 2 — 置信度分布**
统计报告各节（对象/逻辑/动作/规则候选）中置信度为"低"的候选数量和占比。
- 低置信候选占比 > 30% → 生成警告 issue
- 计算公式：低置信数 / 该节总候选数

**维度 3 — 内部一致性**
扫描逻辑候选和动作候选中引用的对象名（如"[[采购订单]]"、"涉及对象"字段），检查是否每个引用名都出现在"业务对象候选"节。
- 不匹配的引用 → 生成 issue，标注引用方和被引用名

**维度 4 — 领域边界**
判断是否有候选明显超出 `DOMAIN_CN` 的领域范围，属于相邻领域概念。
- 仅标注"明显越界"，不要苛求边界模糊的候选

**维度 5 — 属性完整性**
扫描对象候选节的属性表格：
- 属性数量 < 3 的对象 → 生成建议 issue
- 关键字段类型为空的对象 → 生成警告 issue

### Step 3: 输出结构化结果

返回以下 JSON（直接输出，不包裹在代码块外的其他文字）：

```json
{
  "status": "ok",
  "summary": {
    "confidence_distribution": {"高": 0, "中": 0, "低": 0},
    "candidate_counts": {"objects": 0, "logic": 0, "actions": 0, "rules": 0},
    "overall_assessment": "报告整体质量评估一句话描述"
  },
  "issues": [
    {
      "id": "issue-001",
      "dimension": "覆盖度",
      "severity": "警告",
      "target": "入库单",
      "message": "未发现入库相关对象候选，采购领域通常包含此概念",
      "suggestion": "确认是否需要补充入库单对象"
    }
  ]
}
```

字段说明：
- `status`：`"ok"`（无 issue）或 `"partial"`（有 issue）
- `issues[].id`：顺序编号，如 `"issue-001"`、`"issue-002"`
- `issues[].dimension`：`"覆盖度"` / `"置信度分布"` / `"内部一致性"` / `"领域边界"` / `"属性完整性"`
- `issues[].severity`：`"错误"` / `"警告"` / `"建议"`
- `issues[].target`：受影响的候选名称，无特定目标时为 `null`
- `issues[].message`：具体描述，说明发现了什么
- `issues[].suggestion`：建议操作，供专家参考

若 issues 为空，`status` 为 `"ok"`；否则为 `"partial"`。
```

- [ ] **Step 2: 验证文件已创建**

```bash
cat AgentFile/skills/evaluate-research/SKILL.md | head -5
```

期望输出：`<SUBAGENT-STOP>` 开头。

- [ ] **Step 3: Commit**

```bash
git add AgentFile/skills/evaluate-research/SKILL.md
git commit -m "feat: add evaluate-research sub-skill for 5-dimension report quality assessment"
```

---

## Task 2: 重构 interview/SKILL.md

**Files:**
- Modify: `AgentFile/skills/interview/SKILL.md`（完整替换）

- [ ] **Step 1: 替换 SKILL.md 为新版定向补充状态机**

完整替换文件内容为：

```markdown
<SUBAGENT-STOP>
本文件作为 subagent 执行。若你是主 session Claude，请通过 Agent 工具 Dispatch 本 skill，而非直接读取执行。
</SUBAGENT-STOP>

# interview-agent（定向补充模式）

你是一个**定向补充访谈 agent**。你的任务是针对 `CONFIRMED_GAPS` 中已确认的 gap，通过对话引导专家补充信息，写入补充调研文档。

**你不做全量访谈，不写 Ontology 文档，只处理传入的 gap 列表。**

## 输入参数（由 phase-2 在 Dispatch 时传入）

- `CONFIRMED_GAPS`：已确认 gap 列表（JSON 数组，每项含 id / dimension / message / expert_note）
- `RESEARCH_REPORT_PATH`：原调研报告路径（作为上下文，避免重复提问）
- `SUPPLEMENT_OUTPUT_PATH`：补充文档输出路径
- `DOMAIN_CN` / `DOMAIN_EN`：领域信息

## 状态机

```
GAP_ELICITATION → OPEN_FLOOR → CONFIRM → SUMMARY
```

---

## State: GAP_ELICITATION

**目标**：逐 gap 引导专家补充信息。

读取 `RESEARCH_REPORT_PATH`（作为上下文，不展示给用户）。

按 `CONFIRMED_GAPS` 列表顺序，逐条处理每个 gap：

### 按 dimension 选择提问策略

**覆盖度 gap**：
若 `expert_note` 非空，先展示专家已填写的内容确认：
> "您之前提到："{expert_note}"。我来整理一下，这个【{target}】大概是什么业务单据？它有哪些关键信息？"

若 `expert_note` 为空：
> "系统发现【{DOMAIN_CN}】领域通常有【{target}】这个概念，但调研报告里还没有。您们有这个东西吗？如果有，能描述一下它主要包含哪些信息？"

**内部一致性 gap**：
> "报告里的流程引用了【{target}】，但我没找到它的详细定义。它是一张独立的单据，还是流程里的一个节点？"

**属性完整性 gap**：
> "【{target}】目前记录的信息比较少。除了已有的字段，有没有金额、日期、状态这类信息？"

**领域边界 gap**：
> "报告里把【{target}】归入了【{DOMAIN_CN}】，但感觉它可能更偏向相邻领域。这次我们要把它纳入范围，还是先排除？"

### 收集回复并记录

每个 gap 处理完后，在内部 draft 中记录：
```
gap_id: {id}
dimension: {dimension}
expert_input: {专家回复的完整内容}
resolution: included | excluded | deferred
```

---

## State: OPEN_FLOOR

所有 gap 处理完成后，主动开放：

> "以上 {N} 个问题都补充完了。您还有什么想补充或讨论的吗？
> 比如有没有特殊情况、例外规则、或者觉得还没聊到的重要概念？"

若专家继续输入：整理后并入 draft，标注 dimension 为 `"专家主动补充"`。

若专家回复"没有了"/"没了"/"没有"/"no"/"OK" 等结束语：进入 CONFIRM。

---

## State: CONFIRM

展示本次补充内容摘要，请专家确认：

```
本次补充了以下内容：

[gap 处理结果]
  ✓ 覆盖度 — 【入库单】：已补充（{一句话摘要}）
  ✓ 内部一致性 — 【审批记录】：已明确为流程节点，不独立建档
  ✓ 专家主动补充：{简短描述}

  [跳过/排除]
  - 领域边界 — 【财务凭证】：专家确认排除

确认无误后我将保存补充文档。
【确认保存】 【还要修改】
```

若专家选择【还要修改】：返回 GAP_ELICITATION 处理具体修改。

---

## State: SUMMARY

将补充内容写入 `SUPPLEMENT_OUTPUT_PATH`，格式如下：

```markdown
---
type: kea-research-supplement
domain: {DOMAIN_EN}
date: {YYYY-MM-DD}
tags: [kea-research-supplement]
gaps_resolved: {N}
gaps_excluded: {M}
---

# {DOMAIN_CN} 调研补充报告

> 本文档为 Phase 2 定向补充产出，与调研报告（{DOMAIN_EN}-research.md）配合使用。

## 补充对象候选

（仅列出本次新增或修正的候选，格式与调研报告一致）

### {候选名称}
- **来源**：Phase 2 专家访谈补充
- **描述**：{专家提供的描述}
- **关键属性**：{专家提及的属性}
- **备注**：{gap_id} — {gap dimension}

## 补充逻辑候选

（同上，如有）

## 排除项记录

| 候选名称 | 排除原因 |
|---------|---------|
| {名称} | {专家说明} |

## 待确认项（Deferred）

| 候选名称 | 待确认内容 |
|---------|---------|
| {名称} | {说明} |
```

文件写入完成后告知用户：

> "补充文档已保存。接下来 Phase 2 将完成门控评估，确认后进入 Phase 3 流程图生成。"
```

- [ ] **Step 2: 验证文件内容**

```bash
grep "GAP_ELICITATION\|OPEN_FLOOR\|CONFIRM\|SUMMARY" AgentFile/skills/interview/SKILL.md
```

期望输出：4 个状态名均出现。

- [ ] **Step 3: Commit**

```bash
git add AgentFile/skills/interview/SKILL.md
git commit -m "refactor: interview-agent to targeted gap-elicitation mode, remove full interview flow"
```

---

## Task 3: 重写 phase-2-interview.md

**Files:**
- Modify: `AgentFile/phases/phase-2-interview.md`（完整替换）

- [ ] **Step 1: 替换文件为新版编排逻辑**

完整替换为：

```markdown
# Phase 2: 访谈确认（Interview Confirmation）

## 定位

本体萃取技能链第 2 阶段。由 Agent 评估 Phase 1 调研报告质量，专家逐条确认评估建议，按需触发定向补充访谈，产出补充调研文档供后续提取使用。

**强制阶段**：即使有完整源文档，也必须经过专家对报告质量的显式评估与确认。

## 输入参数

| 参数 | 说明 |
|------|------|
| `DOMAIN_CN` | 领域中文名 |
| `DOMAIN_EN` | 领域英文名 |
| `VAULT_PATH` | Vault 路径 |
| `CHAIN_STATE_PATH` | chain-state 文件路径 |
| `RESEARCH_REPORT_PATH` | G1 产出的调研报告路径 |

输出（写入 chain-state 供 Phase 3 使用）：
- `SUPPLEMENT_PATH`：补充文档路径（若有，否则为空）

## 前置条件检查

读取 `CHAIN_STATE_PATH`，确认：
- Phase 1 状态为 `✅ 通过` → 继续
- 否则 → 终止，提示"请先完成并通过 Phase 1（调研）"

## 执行步骤

### Step 1: 更新 chain-state.md 为 in_progress

将 Phase 2 状态更新为 `🔄 进行中`，`last_updated` 更新为当前时间。

### Step 2: Dispatch evaluate-research

读取 `~/.claude/skills/kea/skills/evaluate-research/SKILL.md`，以 Subagent 形式 Dispatch，传入：

```
RESEARCH_REPORT_PATH: {RESEARCH_REPORT_PATH}
DOMAIN_CN: {DOMAIN_CN}
DOMAIN_EN: {DOMAIN_EN}
```

等待返回，解析 JSON 结果。

**若返回 NEEDS_CONTEXT**：展示错误，告知用户检查 Phase 1 报告路径，终止。

### Step 3: 呈现评估结果，专家逐条确认

向用户展示评估摘要：

```
评估完成。{overall_assessment}

候选统计：对象 {N} / 逻辑 {K} / 动作 {M} / 规则 {R}
置信度：高 {H} / 中 {M} / 低 {L}（低置信占比 {X}%）
```

若 `issues` 为空：

```
未发现明显问题，报告质量良好。
```

跳至 Step 5（G2 门控）。

若 `issues` 非空，逐条展示，每条等待专家回复后再展示下一条：

```
发现 {N} 个待确认项，请逐条确认：

第 {i}/{N} 条 [{dimension}]
⚠️  {message}
    建议：{suggestion}

→ A 确认为 gap，需补充
  B 忽略（不在本次范围）
  C 我来说明：[请输入]
```

收集每条回复，汇总为 `CONFIRMED_GAPS`（选 A 或 C 的条目）：

```json
[
  {
    "id": "issue-001",
    "dimension": "覆盖度",
    "message": "未发现入库相关对象候选",
    "expert_note": "（选 C 时的专家输入文本，选 A 时为空字符串）"
  }
]
```

### Step 4: 判断是否需要定向补充

若 `CONFIRMED_GAPS` 为空：告知用户"所有问题已处置，无需补充访谈"，直接进入 Step 6（G2 门控）。

若 `CONFIRMED_GAPS` 非空：

定义补充文档路径：
```
SUPPLEMENT_PATH = {VAULT_PATH}/RAWData/KEAOutput/research/{DOMAIN_EN}-supplement-{YYYY-MM-DD}.md
```

告知用户：
> "已确认 {K} 个 gap，现在开始定向补充访谈。"

读取 `~/.claude/skills/kea/skills/interview/SKILL.md`，以 Subagent 形式 Dispatch，传入：

```
CONFIRMED_GAPS: {CONFIRMED_GAPS JSON}
RESEARCH_REPORT_PATH: {RESEARCH_REPORT_PATH}
SUPPLEMENT_OUTPUT_PATH: {SUPPLEMENT_PATH}
DOMAIN_CN: {DOMAIN_CN}
DOMAIN_EN: {DOMAIN_EN}
```

等待 interview-agent 自然完成（交互型，Phase 2 等待用户与 interview-agent 对话结束）。

### Step 5: 验证补充文档（若有）

若 `CONFIRMED_GAPS` 非空，检查 `SUPPLEMENT_PATH` 文件是否存在：

- **文件存在** → 继续
- **文件不存在** → 访谈可能被中断：
  > "未找到补充文档。是否重新开始定向补充？
  > - ✅ 重新开始
  > - ❌ 跳过补充（在 chain-state 备注中标注"补充未完成"）"

## 门控评估（G2）

### 自动验证项

| 条件 | 检查方式 | 通过标准 |
|------|---------|---------|
| ① 评估已完成 | evaluate-research 返回有效 JSON | status 字段存在且已解析 |
| ② 所有 issue 已处置 | 检查每条 issue 是否有 A/B/C 选择记录 | 无未处置项 |
| ③ 补充文档（按需） | 若 CONFIRMED_GAPS 非空，检查文件存在 | 文件存在且非空；无 gap 时跳过 |
| ④ 候选数量满足 | 读取评估结果中 candidate_counts | objects ≥ 3，logic ≥ 1，actions ≥ 1 |

展示验证结果：

```
自动验证：
  ① 评估完成：✅
  ② issue 全部处置：✅（{N} 条，{K} 条确认为 gap，{M} 条忽略）
  ③ 补充文档：✅ {SUPPLEMENT_PATH}（或"无需补充"）
  ④ 候选数量：✅ 对象 {N}（≥3）/ 逻辑 {K}（≥1）/ 动作 {M}（≥1）
```

如有验证失败项，说明原因，不进入人类确认。

### 人类确认

自动验证全部通过后：

> "评估已完成，gap 已处置。这份调研报告（含补充内容）是否已准确反映了【{DOMAIN_CN}】的核心业务概念，可以进入提取阶段？
>
> - ✅ 确认，可以开始提取
> - ✏️ 还有补充
> - 🔄 重新评估（调研报告质量存疑）"

- **确认** → 门控通过
- **还有补充** → 重新执行 Step 4（增量模式，追加到现有 SUPPLEMENT_PATH）
- **重新评估** → 重新执行 Step 2

## 门控通过 → 更新 chain-state.md

写入 G2 通过记录：

```markdown
| 2 | 访谈确认 | ✅ 通过 | {YYYY-MM-DD HH:MM} | 评估 issue {N} 条，gap 确认 {K} 条，补充文档：{有路径/无} |
```

在"门控记录"节追加：

```markdown
### G2 通过记录（{YYYY-MM-DD HH:MM}）
- 调研报告：research/{DOMAIN_EN}-research.md ✅
- 评估 issue：{N} 条（确认 {K} 条，忽略 {M} 条）
- 补充文档：{SUPPLEMENT_PATH}（若有）✅ / 无需补充
- 人类确认："可以进入提取阶段" ✅
```

在 chain-state.md front matter 中写入（供 Phase 3 读取）：

```yaml
supplement_path: {SUPPLEMENT_PATH}  # 若无补充则留空
```

更新 `current_phase: 3`，`last_updated`。

告知用户：

> "G2 通过。**下一阶段：流程图生成（Phase 3）**
> 是否现在继续？[继续 / 暂停]"

## 门控失败 → 回退处理

**自动验证失败（issue 未全部处置）**：
- 展示未处置的 issue 列表，要求专家逐条确认后重新验证

**自动验证失败（补充文档缺失）**：
- 询问是否重新执行 Step 4

**人类拒绝（需要补充/重新评估）**：
- 按用户指示执行，重新评估

在 chain-state.md 追加回退记录。
```

- [ ] **Step 2: 验证关键结构**

```bash
grep "evaluate-research\|interview/SKILL\|CONFIRMED_GAPS\|SUPPLEMENT_PATH" AgentFile/phases/phase-2-interview.md
```

期望输出：4 个关键词均出现。

- [ ] **Step 3: Commit**

```bash
git add AgentFile/phases/phase-2-interview.md
git commit -m "refactor: phase-2 to evaluation-driven flow with targeted interview on confirmed gaps"
```

---

## Task 4: Phase 3 新增可选 SUPPLEMENT_PATH 输入

**Files:**
- Modify: `AgentFile/phases/phase-3-flowchart-generate.md`（输入参数表 + Step 2）

- [ ] **Step 1: 在输入参数表中新增 SUPPLEMENT_PATH**

在 phase-3 文件的"输入参数"表格中，`INTERVIEW_SUMMARY_PATH` 行之后新增一行：

原文：
```
| `INTERVIEW_SUMMARY_PATH` | G2 访谈摘要路径 |
```

改为：
```
| `INTERVIEW_SUMMARY_PATH` | G2 访谈摘要路径 |
| `SUPPLEMENT_PATH` | 可选，G2 补充调研文档路径（chain-state front matter 中 `supplement_path` 字段，为空时忽略） |
```

- [ ] **Step 2: 在 Step 2（确定流程候选清单）中加入 SUPPLEMENT_PATH 消费逻辑**

找到 Step 2 原文：
```
读取 `INTERVIEW_SUMMARY_PATH`和 `RESEARCH_REPORT_PATH`，从中提取已确认的逻辑/流程列表。
```

改为：
```
读取 `RESEARCH_REPORT_PATH` 和 `INTERVIEW_SUMMARY_PATH`，若 `SUPPLEMENT_PATH` 非空则同时读取补充文档，三份文档合并提取已确认的逻辑/流程候选清单。补充文档中的候选优先级高于调研报告（专家已显式确认）。
```

- [ ] **Step 3: Commit**

```bash
git add AgentFile/phases/phase-3-flowchart-generate.md
git commit -m "feat: phase-3 consumes optional SUPPLEMENT_PATH from phase-2"
```

---

## Task 5: SKILL.md 传参列表新增 SUPPLEMENT_PATH

**Files:**
- Modify: `AgentFile/SKILL.md`

- [ ] **Step 1: 在 Step 4 的传参列表中新增 SUPPLEMENT_PATH**

找到原文：
```
INTERVIEW_SUMMARY_PATH: {VAULT_PATH}/RAWData/KEAOutput/interviews/{DOMAIN_EN}-interview-summary.md
```

在其后新增：
```
SUPPLEMENT_PATH:        {chain-state front matter 中 supplement_path 字段的值，为空时传空字符串}
```

- [ ] **Step 2: 验证**

```bash
grep "SUPPLEMENT_PATH" AgentFile/SKILL.md
```

期望输出：包含 `SUPPLEMENT_PATH` 的行。

- [ ] **Step 3: 在技能链概览中更新 Phase 2 描述**

找到原文：
```
Phase 2  专家访谈      → 强制对话式确认，生成访谈摘要         [不可跳过]
```

改为：
```
Phase 2  专家访谈      → 评估报告质量，专家确认 gap，按需定向补充  [不可跳过]
```

- [ ] **Step 4: Commit**

```bash
git add AgentFile/SKILL.md
git commit -m "feat: pass SUPPLEMENT_PATH from chain-state to phase-3 and beyond"
```

---

## 安装验证

- [ ] **Step 1: 重新安装到 ~/.claude/skills/kea/**

```bash
cd AgentFile && bash install.sh
```

期望输出：包含 `evaluate-research/SKILL.md` 的安装成功提示。

- [ ] **Step 2: 确认新 skill 已安装**

```bash
ls ~/.claude/skills/kea/skills/
```

期望输出：列表中包含 `evaluate-research`。

- [ ] **Step 3: 确认 phase-2 已安装**

```bash
grep "evaluate-research" ~/.claude/skills/kea/phases/phase-2-interview.md
```

期望输出：包含 `evaluate-research` 的行。
