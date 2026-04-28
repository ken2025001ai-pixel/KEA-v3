# Phase 3/4 重设计：生成型 sub-skill + 确定性结构校验

## 背景与问题

Phase 3/4 存在三个架构性问题：

**P1**：Phase 3 由 phase 文件自己生成 Mermaid 代码并写文件，违反"生成型任务应 Dispatch sub-skill"的架构原则，phase 文件同时承担"编排"和"生成"两个职责。

**P2**：Phase 3 逐图展示 Mermaid 代码等待确认，体验差且效率低——专家需要在 Obsidian 渲染图中查看，而不是在 chat 中看原始代码。

**P3/P4**：Phase 3 G3 的结构验证项 ③④（START/END 节点存在、判断节点出路）由 LLM 读取解析结果自行判断；Phase 4 Phase A 的 S1-S4 结构校验同样是 LLM 扮演确定性检查器——违反"能用工具校验的必须用工具"原则。

## 变更方案（方案 B：防御性重跑）

Phase 3 G3 和 Phase 4 Phase A 均运行 `kea flowchart-check`。批量确认阶段用户可能直接在 Obsidian 编辑文件，Phase 4 重跑作为安全网。

---

## 设计一：Phase 3 整体流程重构

### 新流程

```
Step 1  更新 chain-state 为 in_progress
Step 2  读取源文档 → 提取流程候选 → 展示给用户确认范围 → 得到 CONFIRMED_CANDIDATES
Step 3  Dispatch generate-flowcharts sub-skill（传入 CONFIRMED_CANDIDATES）
Step 4  运行 kea flowchart-check → 结构问题修复循环
Step 5  批量人类确认（引导去 Obsidian 查看，回来一次性反馈）
G3     门控（kea flowchart-check + 人类确认记录）
```

### 与原设计的关键差异

| 原设计 | 新设计 |
|--------|--------|
| Phase 文件自己生成 Mermaid | Dispatch generate-flowcharts sub-skill |
| 逐图확인在 chat 中 | 批量确认，引导 Obsidian 查看 |
| G3 结构验证由 LLM 判断 | `kea flowchart-check` 确定性工具 |

### Step 2 详细：候选清单提取与确认

Phase 3 读取 `RESEARCH_REPORT_PATH`、`INTERVIEW_SUMMARY_PATH`（若有 `SUPPLEMENT_PATH` 一并读取），提取已确认的逻辑/流程候选，展示给用户：

```
流程候选清单（共 {N} 个）：

  【P1】{流程名} — {一句话描述}
  【P2】{流程名} — {一句话描述}
  ...

  已有流程图（如有）：
  ✅ 【P3】{流程名} — 已存在，保留 / 重新生成？

请确认生成范围：
  ✅ 生成全部（{N} 个）
  🔄 仅生成缺失部分
  ➕ 添加：[描述]
  ✂️ 移除：[P{n}]
```

用户确认后得到 `CONFIRMED_CANDIDATES`（含流程名 + 一句话描述列表），传入 sub-skill。

### Step 4/5 详细：结构校验 + 批量确认

**Step 4**：运行 `kea flowchart-check`，若有失败项展示并引导修复，修复后重跑直到全部通过。

**Step 5**：

```
{N} 个流程图已生成并通过结构校验。

请在 Obsidian 中查看渲染后的流程图：
  📁 diagrams/{DOMAIN_EN}/

所有流程图审阅完毕后，请回复：
  ✅ 全部确认
  ✏️ 需要调整：[列出流程名 + 具体修改]
```

用户回来后，若有调整则由 Phase 3 直接修改对应 Mermaid 文件（逐项处理），修改后重跑 `kea flowchart-check` 确认无结构破坏，再次引导用户确认。

---

## 设计二：generate-flowcharts sub-skill（新增）

**类型：** 生成型（DONE / DONE_WITH_CONCERNS / NEEDS_CONTEXT / BLOCKED）

### 输入参数

| 参数 | 说明 |
|------|------|
| `CONFIRMED_CANDIDATES` | 用户确认的流程清单（JSON 数组，每项含 name + description） |
| `RESEARCH_REPORT_PATH` | 调研报告路径 |
| `INTERVIEW_SUMMARY_PATH` | 访谈摘要路径 |
| `SUPPLEMENT_PATH` | 可选，补充调研文档路径 |
| `DIAGRAMS_DIR` | 输出目录（已含领域名，格式：`.../diagrams/{DOMAIN_EN}/`） |
| `DOMAIN_CN` / `DOMAIN_EN` | 领域信息 |
| `EXISTING_FILES` | 已有流程图文件列表（增量模式时传入，避免重复生成） |

### 执行逻辑

读取全部源文档作为上下文，按 `CONFIRMED_CANDIDATES` 列表逐一生成 Mermaid 流程图，写入 `{DIAGRAMS_DIR}/{流程名}.md`。

**Mermaid 节点约定（写入 SKILL.md）：**

| 形状语法 | 节点类型 | 约束 |
|---------|---------|------|
| `((开始\n输入: {参数}))` | 开始节点 | 每图唯一 |
| `((结束\n输出: {结果}))` | 结束节点 | 至少一个 |
| `[动作描述]` | 动作节点 | — |
| `(活动描述)` | 活动节点 | — |
| `{条件?}` | 判断节点 | 必须有"是"/"否"两条出路 |
| `[[子流程名称]]` | 子流程引用 | 名称须与已有流程图一致 |

**每个文件带 YAML frontmatter：**
```yaml
---
domain: {DOMAIN_EN}
process: {流程名}
phase: flowchart
created_at: {YYYY-MM-DD}
---
```

### 返回格式

**DONE：**
```
状态：DONE

生成统计：{N} 个流程图
  ✅ 创建采购订单 → diagrams/{DOMAIN_EN}/创建采购订单.md
  ✅ 审批采购申请 → diagrams/{DOMAIN_EN}/审批采购申请.md
```

**DONE_WITH_CONCERNS（来源描述不足）：**
```
状态：DONE_WITH_CONCERNS

生成统计：{N} 个流程图（{K} 个存在疑虑）

疑虑清单：
- 入库确认流程：来源文档对该流程描述不足，关键判断节点（数量不符时的处理）基于模型推断，置信度低
```

**NEEDS_CONTEXT：**
```
状态：NEEDS_CONTEXT
缺少信息：CONFIRMED_CANDIDATES 为空，无法确定需要生成哪些流程图
```

---

## 设计三：kea flowchart-check 命令（新增）

**新增 Python 命令**，对 Mermaid flowchart 文件执行 S1-S4 结构校验。

### 命令形式

```bash
python3 -m kea flowchart-check {DIAGRAMS_DIR} --format json  # 目录，扫描所有 .md
python3 -m kea flowchart-check {单个.md} --format json       # 单文件
```

### S1-S4 检查项

| 检查 | 通过标准 | 取自解析结果 |
|------|---------|------------|
| S1 START 数量 | 有且仅有 1 个 | nodes 中 type=start 的数量 |
| S2 END 存在 | 至少 1 个 | nodes 中 type=end 的数量 |
| S3 判断节点分支数 | 每个 decision/sub_decision 出路 ≥ 2 | decision_branches 映射 |
| S4 无孤立节点 | 所有节点有入路（除 START），所有节点有出路（除 END） | 遍历 edges 计算入度/出度 |

### 输出格式

```json
{
  "summary": {"total": 3, "passed": 2, "failed": 1},
  "results": [
    {
      "file": "创建采购订单.md",
      "passed": true,
      "issues": []
    },
    {
      "file": "审批采购申请.md",
      "passed": false,
      "issues": [
        {
          "check": "S3",
          "node_id": "d2",
          "node_label": "是否超预算?",
          "message": "判断节点只有 1 条出路，需要 ≥ 2"
        }
      ]
    }
  ]
}
```

### 实现位置

- 新文件：`kea/validator/flowchart_checker.py`（FlowchartChecker 类，复用 mermaid_parser.py）
- 修改：`kea/cli.py` 注册 `flowchart-check` 子命令

---

## 设计四：Phase 4 Phase A 变更

### 原 Phase A

LLM 读取 `kea mermaid` 解析结果，自行判断 S1-S4 是否满足。

### 新 Phase A

调用 `kea flowchart-check`，结果确定性输出，LLM 只负责呈现和修复引导。

**新 Step A1：**

```bash
cd {PROJECT_ROOT} && python3 -m kea --format json flowchart-check {DIAGRAMS_DIR}
```

读取 JSON，若 `summary.failed > 0`，展示：

```
[结构校验] {N} 个流程图存在结构问题：

  审批采购申请.md：
    ❌ [S3] 判断节点 "是否超预算?" 只有 1 条出路（需要 ≥ 2）

请修复后回复"继续"重新校验。
```

修复后重跑，循环直到 `summary.failed = 0`。

**Step A2 废弃**（原 LLM 做 S1-S4 判断逻辑，由工具替代）。

**Phase B 不变**（flowchart-validate semantic sub-skill 逻辑不变）。

---

## 涉及文件变更

| 操作 | 文件路径 | 说明 |
|------|---------|------|
| 新增 | `AgentFile/skills/generate-flowcharts/SKILL.md` | 生成型 sub-skill，一次性生成所有流程图 |
| 重写 | `AgentFile/phases/phase-3-flowchart-generate.md` | 新编排：候选确认 → sub-skill 生成 → 批量确认 |
| 小改 | `AgentFile/phases/phase-4-flowchart-validate.md` | Phase A 改用 `kea flowchart-check` |
| 新增 | `kea/validator/flowchart_checker.py` | S1-S4 结构校验逻辑 |
| 修改 | `kea/cli.py` | 注册 `flowchart-check` 子命令 |
