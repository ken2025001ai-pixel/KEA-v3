# Phase 5-8 Unified Extraction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 Phase 5/6/7/8 四个独立提取 Phase 合并为一个 `phase-5-extract-ontology.md`，以序列静默流水线模式执行，正常情况只有 1 次用户确认，硬性错误才额外交互。

**Architecture:** 新建 `phase-5-extract-ontology.md` 编排四个 Subagent（objects→logic→actions→rules），每个 Subagent 完成后立即运行 `kea validate` 硬门检查（errors=0 且 dead_links=0），通过则静默继续，失败则中断告知用户。所有类型全部完成后展示一次综合摘要，专家确认一次。四个专项 SKILL.md（extract-objects/logic/actions/rules）保持不变。SKILL.md 路由表 phase 5 指向新文件，phase 6/7/8 入口移除，chain-state.md 进度展示和初始化模板同步更新。

**Tech Stack:** Markdown（AgentFile 编排层），无 Python 工具层改动

---

## File Map

| 文件 | 改动类型 | 说明 |
|---|---|---|
| `AgentFile/phases/phase-5-extract-ontology.md` | **Create** | 新的统一提取 Phase |
| `AgentFile/phases/phase-5-extract-objects.md` | **Delete** | 废弃，内容已迁移 |
| `AgentFile/phases/phase-6-extract-logic.md` | **Delete** | 废弃，内容已迁移 |
| `AgentFile/phases/phase-7-extract-actions.md` | **Delete** | 废弃，内容已迁移 |
| `AgentFile/phases/phase-8-extract-rules.md` | **Delete** | 废弃，内容已迁移 |
| `AgentFile/SKILL.md` | **Modify** | 路由表 + 进度展示 + chain-state 初始化模板 |
| `AgentFile/skills/extract-objects/SKILL.md` | No change | — |
| `AgentFile/skills/extract-logic/SKILL.md` | No change | — |
| `AgentFile/skills/extract-actions/SKILL.md` | No change | — |
| `AgentFile/skills/extract-rules/SKILL.md` | No change | — |

---

## Task 1：创建 phase-5-extract-ontology.md

**Files:**
- Create: `AgentFile/phases/phase-5-extract-ontology.md`

这是核心任务。新文件需要编排整个提取流水线，包含预处理、四个 Subagent dispatch、硬门检查、最终综合确认。

- [ ] **Step 1: 创建文件，写入定位和输入参数表**

创建 `AgentFile/phases/phase-5-extract-ontology.md`，写入以下内容：

````markdown
# Phase 5: 本体提取（Ontology Extraction）

## 定位

本体萃取技能链第 5 阶段。基于已校验的流程图、调研报告和访谈摘要，依次提取四类本体文档：**业务对象 → 业务逻辑 → 业务动作 → 业务规则**。

每类提取完成后立即运行结构校验（硬门）。全部通过后，专家进行一次综合确认。

## 输入参数

| 参数 | 说明 |
|------|------|
| `DOMAIN_CN` / `DOMAIN_EN` | 领域名 |
| `VAULT_PATH` | Vault 路径 |
| `CHAIN_STATE_PATH` | chain-state 文件路径 |
| `RESEARCH_REPORT_PATH` | G1 调研报告路径 |
| `INTERVIEW_SUMMARY_PATH` | G2 访谈摘要路径 |
| `DIAGRAMS_DIR` | G3/G4 已校验流程图目录 |
| `OBJECTS_DIR` | `{VAULT_PATH}/30-Ontology/objects/{DOMAIN_EN}/` |
| `LOGIC_DIR` | `{VAULT_PATH}/30-Ontology/logic/{DOMAIN_EN}/` |
| `ACTIONS_DIR` | `{VAULT_PATH}/30-Ontology/actions/{DOMAIN_EN}/` |
| `RULES_DIR` | `{VAULT_PATH}/30-Ontology/rules/{DOMAIN_EN}/` |
| `COVERAGE_THRESHOLD` | 覆盖率阈值，默认 80（读自 chain-state.md front matter） |

## 前置条件检查

读取 `CHAIN_STATE_PATH`，确认：

- Phase 4（或 Phase 3，若跳过 Phase 4）状态为 `✅ 通过` → 继续
- 否则 → 终止，提示需先完成 Phase 3/4（流程图生成与校验）
````

- [ ] **Step 2: 写入 Step 1-3（模式判断 + chain-state 更新 + 预处理）**

在文件末尾追加：

````markdown
## 执行步骤

### Step 1: 确定提取模式

分别检查四个输出目录是否已有文件：

- `OBJECTS_DIR` 有文件 → objects 以 `MODE=incremental` 运行，收集 `EXISTING_OBJECTS`
- `LOGIC_DIR` 有文件 → logic 以 `MODE=incremental` 运行，收集 `EXISTING_LOGICS`
- `ACTIONS_DIR` 有文件 → actions 以 `MODE=incremental` 运行，收集 `EXISTING_ACTIONS`
- `RULES_DIR` 有文件 → rules 以 `MODE=incremental` 运行，收集 `EXISTING_RULES`
- 全部为空 → 全量模式

若有增量目录，告知用户："检测到已有文件，对应类型将以增量模式补充提取。"

### Step 2: 更新 chain-state.md 为 in_progress

将 phases 5/6/7/8 均设为 `🔄 进行中`。

### Step 3: 一次性预处理所有源文档

**工具调用 1**：扫描流程图（objects 和 logic 共用）

```bash
python3 -m kea --format json mermaid {DIAGRAMS_DIR}
```

**成功**（`count > 0`）→ 构建 `FLOWCHART_CANDIDATES` 文本（格式：文件名 + 节点列表 + 边标签列表）。

**失败** → 询问用户：A 检查路径后重试 / B 跳过（subagent 将无流程图候选，基于文字摘要提取）

---

**工具调用 2**：预读已有对象（incremental 模式时，供 logic/actions/rules 使用）

若 `OBJECTS_DIR` 下已有文件：

```bash
python3 -m kea --format json parse {OBJECTS_DIR}
```

**成功** → 构建 `OBJECT_REGISTRY` 文本（格式：对象名(id) + 属性列表）。

**失败** → 询问用户 A/B，B 时 OBJECT_REGISTRY 留空。

---

**工具调用 3**：预读已有逻辑（incremental 模式时，供 actions/rules 使用）

若 `LOGIC_DIR` 下已有文件（incremental 模式）：

```bash
python3 -m kea --format json parse {LOGIC_DIR}
```

**成功** → 构建 `LOGIC_REGISTRY` 文本（格式：逻辑名(id) + 关联动作 + 输入对象 + 输出对象）。

**失败** → 询问用户 A/B，B 时 LOGIC_REGISTRY 留空。

---

**工具调用 4**：预读已有动作（incremental 模式时，供 rules 使用）

若 `ACTIONS_DIR` 下已有文件（incremental 模式）：

```bash
python3 -m kea --format json parse {ACTIONS_DIR}
```

**成功** → 构建 `ACTION_REGISTRY` 文本（格式：动作名(id) + 所属逻辑 + 输入约束 + 操作对象）。

**失败** → 询问用户 A/B，B 时 ACTION_REGISTRY 留空。

> 注：全量模式时 OBJECT_REGISTRY / LOGIC_REGISTRY / ACTION_REGISTRY 初始为空，随流水线推进逐步填充（Step 4b-4d 的 dispatch 参数从前一步的校验结果中提取）。
````

- [ ] **Step 3: 写入 Step 4a（对象提取 + 硬门）**

追加：

````markdown
### Step 4a: 对象提取

**Dispatch extract-objects Subagent**

读取 `~/.claude/skills/kea/skills/extract-objects/SKILL.md`，Dispatch：

```
FLOWCHART_CANDIDATES: {Step 3 工具调用 1 生成的文本}
SUMMARY_PATHS: {RESEARCH_REPORT_PATH},{INTERVIEW_SUMMARY_PATH}
OBJECTS_DIR: {OBJECTS_DIR}
EXISTING_FILES: {EXISTING_OBJECTS（incremental 时）}
```

处理返回状态：
- **DONE / DONE_WITH_CONCERNS** → 若有 concerns，展示并等待用户逐项处置，完成后继续
- **NEEDS_CONTEXT** → 展示缺失信息，补充后重新 Dispatch
- **BLOCKED** → 展示卡点，询问用户处置方式

**硬门检查（自动，不打断用户）**

```bash
cd {PROJECT_ROOT} && python3 -m kea --format json validate {OBJECTS_DIR}
```

- `errors = 0` 且 dead_links（category=`引用失效`）= 0 → **静默继续 Step 4b**
- 任一不满足 → 展示错误明细，等待用户指令（修复后重跑校验，或中止整个流水线）

**校验通过后**：运行 `kea parse {OBJECTS_DIR}` 更新 `OBJECT_REGISTRY`，供后续步骤使用。

```bash
python3 -m kea --format json parse {OBJECTS_DIR}
```
````

- [ ] **Step 4: 写入 Step 4b（逻辑提取 + 硬门）**

追加：

````markdown
### Step 4b: 逻辑提取

**收集动作候选前置**（供 Step 4c 使用）：逻辑提取完成后，从逻辑文档中收集 `REFERENCED_ACTIONS`（从"与动作关联"表和 `call_action` 伪代码中提取，去重）。

**Dispatch extract-logic Subagent**

读取 `~/.claude/skills/kea/skills/extract-logic/SKILL.md`，Dispatch：

```
FLOWCHART_CANDIDATES: {Step 3 工具调用 1 生成的文本}
OBJECT_REGISTRY: {Step 4a 校验后更新的 OBJECT_REGISTRY}
SUMMARY_PATHS: {RESEARCH_REPORT_PATH},{INTERVIEW_SUMMARY_PATH}
LOGIC_DIR: {LOGIC_DIR}
EXISTING_FILES: {EXISTING_LOGICS（incremental 时）}
```

处理返回状态（同 Step 4a 模式）。

**硬门检查（自动）**

```bash
cd {PROJECT_ROOT} && python3 -m kea --format json validate {LOGIC_DIR}
```

- `errors = 0` 且 dead_links = 0 → **静默继续**
- 任一不满足 → 展示错误明细，等待用户指令

**校验通过后**：
1. 运行 `kea parse {LOGIC_DIR}` 更新 `LOGIC_REGISTRY`
2. 从逻辑文档收集 `REFERENCED_ACTIONS`（扫描各文件"与动作(action)的关联"表 + 伪代码中 `call_action` 调用，去重）

```bash
python3 -m kea --format json parse {LOGIC_DIR}
```
````

- [ ] **Step 5: 写入 Step 4c（动作提取 + 硬门）**

追加：

````markdown
### Step 4c: 动作提取

**Dispatch extract-actions Subagent**

读取 `~/.claude/skills/kea/skills/extract-actions/SKILL.md`，Dispatch：

```
REFERENCED_ACTIONS: {Step 4b 收集的动作候选列表文本}
LOGIC_REGISTRY: {Step 4b 校验后更新的 LOGIC_REGISTRY}
OBJECT_REGISTRY: {Step 4a 校验后更新的 OBJECT_REGISTRY}
ACTIONS_DIR: {ACTIONS_DIR}
SUMMARY_PATHS: {RESEARCH_REPORT_PATH},{INTERVIEW_SUMMARY_PATH}
EXISTING_FILES: {EXISTING_ACTIONS（incremental 时）}
```

处理返回状态（同 Step 4a 模式）。

**硬门检查（自动）**

```bash
cd {PROJECT_ROOT} && python3 -m kea --format json validate {ACTIONS_DIR}
```

- `errors = 0` 且 dead_links = 0 → **静默继续**
- 任一不满足 → 展示错误明细，等待用户指令

**校验通过后**：运行 `kea parse {ACTIONS_DIR}` 更新 `ACTION_REGISTRY`。

```bash
python3 -m kea --format json parse {ACTIONS_DIR}
```
````

- [ ] **Step 6: 写入 Step 4d（规则候选扫描 + 规则提取 + 硬门）**

追加：

````markdown
### Step 4d: 规则提取

**规则候选预扫描**（LLM 读取已有文档，无需工具调用）：

扫描 objects/logic/actions 文档，识别潜在规则候选：
- 逻辑文档判断节点中的数值阈值条件（金额 > N、数量 > N）
- 逻辑/动作描述中包含"必须"/"不得"/"要求"的句子
- 动作文档中 required=是 的参数隐含的校验规则

展示候选清单并询问用户：
- ✅ 全部提取
- 🗑️ 排除 {编号}
- ➕ 补充
- ❌ 该领域无独立规则 → 跳过 Dispatch，直接进入 Step 5 确认

**Dispatch extract-rules Subagent**（仅当有候选规则时）

读取 `~/.claude/skills/kea/skills/extract-rules/SKILL.md`，Dispatch：

```
RULE_CANDIDATES: {用户确认后的规则候选列表文本}
LOGIC_REGISTRY: {Step 4b 校验后更新的 LOGIC_REGISTRY}
ACTION_REGISTRY: {Step 4c 校验后更新的 ACTION_REGISTRY}
OBJECT_REGISTRY: {Step 4a 校验后更新的 OBJECT_REGISTRY}
RULES_DIR: {RULES_DIR}
SUMMARY_PATHS: {RESEARCH_REPORT_PATH}
EXISTING_FILES: {EXISTING_RULES（incremental 时）}
```

处理返回状态（同 Step 4a 模式）。

**硬门检查（自动，仅当 RULES_DIR 下有文件时）**

```bash
cd {PROJECT_ROOT} && python3 -m kea --format json validate {RULES_DIR}
```

- `errors = 0` 且 dead_links = 0 → **静默继续**
- 任一不满足 → 展示错误明细，等待用户指令
````

- [ ] **Step 7: 写入 Step 5（综合摘要 + 单次专家确认）和门控通过更新**

追加：

````markdown
### Step 5: 综合摘要与专家确认

展示全部提取结果摘要：

```
本体提取完成。请在 Obsidian 中审视以下内容，然后确认：

  📂 对象（{N_obj} 个）：30-Ontology/objects/{DOMAIN_EN}/
  📂 逻辑（{N_log} 个）：30-Ontology/logic/{DOMAIN_EN}/
  📂 动作（{N_act} 个）：30-Ontology/actions/{DOMAIN_EN}/
  📂 规则（{N_rul} 个，或"无独立规则"）：30-Ontology/rules/{DOMAIN_EN}/

  Graph View 可查看完整关系网络：
    红色 = 对象  蓝色 = 逻辑  绿色 = 动作  橙色 = 规则

  自动校验结果：
    结构错误：0 ✅  死链：0 ✅（全部四类）

审视完毕后请确认：
  ✅ 确认：本体提取准确完整，进入校验阶段
  ✏️ 需要修改 {文件名}：[说明]
  ➕ 缺少 {名称}：[说明业务含义]
```

- **确认** → 门控通过，进入 Step 6
- **需要修改** → 执行修改 → 重新运行对应类型的 `kea validate` → 询问是否继续
- **缺少** → 对应类型增量 re-extract（回到 Step 4x）→ 硬门 → 回到 Step 5

### Step 6: 更新 chain-state.md

将 phases 5/6/7/8 全部标记为通过，更新 `current_phase: 9`：

```markdown
| 5 | 对象提取 | ✅ 通过 | {YYYY-MM-DD HH:MM} | {N_obj}个，结构错误0，死链0 |
| 6 | 逻辑提取 | ✅ 通过 | {YYYY-MM-DD HH:MM} | {N_log}个，结构错误0，死链0 |
| 7 | 动作提取 | ✅ 通过 | {YYYY-MM-DD HH:MM} | {N_act}个，结构错误0，死链0 |
| 8 | 规则提取 | ✅ 通过 | {YYYY-MM-DD HH:MM} | {N_rul}个（或"无独立规则"），结构错误0 |
```

门控记录追加：

```markdown
### G5-G8 通过记录（{YYYY-MM-DD HH:MM}）
- 对象：{N_obj} 个，结构错误 0，死链 0 ✅
- 逻辑：{N_log} 个，结构错误 0，死链 0 ✅
- 动作：{N_act} 个，结构错误 0，死链 0 ✅
- 规则：{N_rul} 个（或"无独立规则，已确认"），结构错误 0 ✅
- 人类确认：{用户确认内容摘要} ✅
```

## 门控失败 → 回退处理

硬门失败时（任意 Step 4x 的 kea validate 返回 errors > 0 或 dead_links > 0）：

| 失败位置 | 优先处理方式 | 无法修复时回退目标 |
|---------|------------|-----------------|
| Step 4a 对象硬门 | 当前阶段内修复文件 | Phase 4（流程图） |
| Step 4b 逻辑硬门（dead_links） | 检查 [[链接]] 是否指向已有对象 → Phase 5（对象）补充 | Phase 4 |
| Step 4c 动作硬门 | 当前阶段内修复文件 | Phase 5-6 补充逻辑/对象 |
| Step 4d 规则硬门 | 当前阶段内修复文件 | Phase 5/6/7 补充对应文件 |
````

- [ ] **Step 8: 验证文件结构**

```bash
grep -n "^### Step\|^## " /Users/kenkangning/KEA-v3/AgentFile/phases/phase-5-extract-ontology.md
```

期望输出包含（顺序正确）：
```
## 定位
## 输入参数
## 前置条件检查
## 执行步骤
### Step 1
### Step 2
### Step 3
### Step 4a
### Step 4b
### Step 4c
### Step 4d
### Step 5
### Step 6
## 门控失败
```

- [ ] **Step 9: Commit**

```bash
cd /Users/kenkangning/KEA-v3
git add AgentFile/phases/phase-5-extract-ontology.md
git commit -m "feat: create phase-5-extract-ontology unified extraction pipeline"
```

---

## Task 2：删除废弃的 Phase 5/6/7/8 旧文件

**执行顺序：Task 1 → Task 3 → Task 2 → Task 4**（本 Task 必须在 Task 1 和 Task 3 完成、验证通过后执行）

**Files:**
- Delete: `AgentFile/phases/phase-5-extract-objects.md`
- Delete: `AgentFile/phases/phase-6-extract-logic.md`
- Delete: `AgentFile/phases/phase-7-extract-actions.md`
- Delete: `AgentFile/phases/phase-8-extract-rules.md`

- [ ] **Step 1: 删除四个旧 Phase 文件**

```bash
cd /Users/kenkangning/KEA-v3
rm AgentFile/phases/phase-5-extract-objects.md
rm AgentFile/phases/phase-6-extract-logic.md
rm AgentFile/phases/phase-7-extract-actions.md
rm AgentFile/phases/phase-8-extract-rules.md
```

- [ ] **Step 2: 验证 phases/ 目录**

```bash
ls AgentFile/phases/
```

期望：`phase-1-research.md` 到 `phase-4-flowchart-validate.md`，`phase-5-extract-ontology.md`，`phase-9-rule-check.md` 到 `phase-12-scenario-trace.md`。无旧的 phase-5/6/7/8 文件。

- [ ] **Step 3: Commit**

```bash
git add -A AgentFile/phases/
git commit -m "refactor: remove deprecated phase-5/6/7/8 individual extraction files"
```

---

## Task 3：更新 SKILL.md 路由表和进度展示

**Files:**
- Modify: `AgentFile/SKILL.md`

SKILL.md 有三处需要修改：
1. 路由表（Step 4）：phase 5 指向新文件，phase 6/7/8 入口移除
2. 进度展示模板（Step 3 文件存在时的展示）：phase 6/7/8 合并进 phase 5 展示
3. chain-state.md 初始化模板（Step 3 文件不存在时）：phase 6/7/8 行移除

- [ ] **Step 1: 更新路由表**

在 `AgentFile/SKILL.md` 中，找到路由表：

```
| 5 | `~/.claude/skills/kea/phases/phase-5-extract-objects.md` |
| 6 | `~/.claude/skills/kea/phases/phase-6-extract-logic.md` |
| 7 | `~/.claude/skills/kea/phases/phase-7-extract-actions.md` |
| 8 | `~/.claude/skills/kea/phases/phase-8-extract-rules.md` |
```

替换为：

```
| 5 | `~/.claude/skills/kea/phases/phase-5-extract-ontology.md` |
```

（删除 6/7/8 三行）

- [ ] **Step 2: 更新进度展示示例**

找到 Step 3 中"若文件存在"部分的进度展示示例，将：

```
  Phase 5  对象提取      ✅ 通过  2026-04-21（共 12 个对象）
  Phase 6  逻辑提取      ✅ 通过  2026-04-21（共 8 个逻辑）
  Phase 7  动作提取      🔄 进行中
  Phase 8  规则提取      ⏳ 待执行
```

替换为：

```
  Phase 5  本体提取      ✅ 通过  2026-04-21（对象12 逻辑8 动作20 规则3）
```

（Phase 5 合并展示四类计数，Phase 6/7/8 行移除）

同时将示例中 `→ 继续执行 Phase 7（动作提取）` 类似的引导语调整为实际情况（若 phase 5 in_progress，显示 `→ 继续执行 Phase 5（本体提取）`）。

- [ ] **Step 3: 更新 chain-state 初始化模板**

找到 Step 3"若文件不存在"部分的初始化模板表格，将：

```
| 5 | 对象提取 | ⏳ 待执行 | — | — |
| 6 | 逻辑提取 | ⏳ 待执行 | — | — |
| 7 | 动作提取 | ⏳ 待执行 | — | — |
| 8 | 规则提取 | ⏳ 待执行 | — | — |
```

替换为：

```
| 5 | 本体提取 | ⏳ 待执行 | — | — |
```

- [ ] **Step 4: 更新技能链概览**

找到 `## 技能链概览` 的代码块，将：

```
Phase 5  对象提取      → 提取所有业务对象，覆盖率≥80%
Phase 6  逻辑提取      → 提取业务流程，死链=0（最高优先级）
Phase 7  动作提取      → 提取动作，引用动作100%覆盖
Phase 8  规则提取      → 提取业务规则（允许零规则但需确认）
```

替换为：

```
Phase 5  本体提取      → 对象→逻辑→动作→规则流水线，每类硬门 errors=0+dead_links=0，最终1次专家确认
```

Phase 6/7/8 行全部删除，后续 Phase 编号不变（Phase 9 仍为结构校验）。

- [ ] **Step 5: 验证修改**

```bash
grep -n "phase-5\|phase-6\|phase-7\|phase-8\|本体提取\|对象提取\|逻辑提取\|动作提取\|规则提取" /Users/kenkangning/KEA-v3/AgentFile/SKILL.md
```

期望：
- `phase-5-extract-ontology` 出现 1 次（路由表）
- `phase-6/7/8` 不出现
- `本体提取` 出现（进度展示 + 概览）
- `对象提取/逻辑提取/动作提取/规则提取` 不出现（或仅出现在 done 状态的统计展示中）

- [ ] **Step 6: Commit**

```bash
git add AgentFile/SKILL.md
git commit -m "refactor: SKILL.md route phase5-8 to unified extract-ontology phase"
```

---

## Task 4：全量验证

**Files:** 无新改动

- [ ] **Step 1: 运行全量测试**

```bash
cd /Users/kenkangning/KEA-v3
python3 -m pytest tests/ -q 2>&1 | tail -10
```

期望：全部 PASSED，无失败。

- [ ] **Step 2: kea lint AgentFile**

```bash
python3 -m kea --format json lint AgentFile/ 2>&1 | python3 -c "import sys,json; d=json.load(sys.stdin); print('errors:', d.get('summary',{}).get('errors',0))"
```

期望：`errors: 0`

- [ ] **Step 3: 验证新 Phase 文件存在、旧文件已删除**

```bash
ls AgentFile/phases/
```

期望：`phase-5-extract-ontology.md` 存在，`phase-5-extract-objects.md`、`phase-6/7/8` 不存在。

- [ ] **Step 4: 验证 chain-state 初始化模板行数**

```bash
grep -c "待执行" AgentFile/SKILL.md
```

期望：`9`（Phase 1-5 + Phase 9-12，共 9 行）。

- [ ] **Step 5: 最终 commit（若有遗漏改动）**

```bash
git status
# 若有未提交改动：
git add -A
git commit -m "chore: finalize phase5-8 unified extraction refactor"
```
