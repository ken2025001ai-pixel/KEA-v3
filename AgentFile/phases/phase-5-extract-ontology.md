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

**成功**（`count > 0`）→ 构建 `FLOWCHART_CANDIDATES` 文本：

```
流程图扫描结果（{count} 个文件，{总节点数} 个节点，{总边数} 条边）：

文件：{chart.file}
  节点：{label}[{type}], {label}[{type}] ...
  边标签：{edge.label}, {edge.label} ...（仅非空 label）
```

**失败** → 询问用户：A 检查路径后重试 / B 跳过（subagent 将无流程图候选，基于文字摘要提取）

---

**工具调用 2**：预读已有对象（incremental 模式时，供 logic/actions/rules 使用）

若 `OBJECTS_DIR` 下已有文件：

```bash
python3 -m kea --format json parse {OBJECTS_DIR}
```

**成功** → 构建 `OBJECT_REGISTRY` 文本（格式：对象名(id) + 属性列表）：

```
已确认对象（{N} 个）：

{对象名} (id={id})
  属性：{属性名}[{类型},主键], {属性名}[{类型}] ...
```

**失败** → 询问用户 A 重试 / B 跳过（OBJECT_REGISTRY 留空）。

---

**工具调用 3**：预读已有逻辑（incremental 模式时，供 actions/rules 使用）

若 `LOGIC_DIR` 下已有文件：

```bash
python3 -m kea --format json parse {LOGIC_DIR}
```

**成功** → 构建 `LOGIC_REGISTRY` 文本：

```
已确认逻辑（{N} 个）：

{逻辑名} (id={id})
  关联动作：{动作名1}, {动作名2} ...
  输入对象：{对象名1}, {对象名2} ...
  输出对象：{对象名1} ...
```

**失败** → 询问用户 A/B，B 时 LOGIC_REGISTRY 留空。

---

**工具调用 4**：预读已有动作（incremental 模式时，供 rules 使用）

若 `ACTIONS_DIR` 下已有文件：

```bash
python3 -m kea --format json parse {ACTIONS_DIR}
```

**成功** → 构建 `ACTION_REGISTRY` 文本：

```
已确认动作（{N} 个）：

{动作名} (id={id})
  所属逻辑：{逻辑名} (id={id})
  输入约束：{参数名}[{类型},required={true|false}] ...
  操作对象：{对象名}[uses|modifies] ...
```

**失败** → 询问用户 A/B，B 时 ACTION_REGISTRY 留空。

> 注：全量模式时 OBJECT_REGISTRY / LOGIC_REGISTRY / ACTION_REGISTRY 初始为空，随流水线推进逐步填充（Step 4a-4c 的硬门通过后更新）。

### Step 4a: 对象提取

**Dispatch extract-objects Subagent**

读取 `~/.claude/skills/kea/skills/extract-objects/SKILL.md`，以 Subagent 形式 Dispatch：

```
FLOWCHART_CANDIDATES: {Step 3 工具调用 1 生成的文本}
SUMMARY_PATHS: {RESEARCH_REPORT_PATH},{INTERVIEW_SUMMARY_PATH}
OBJECTS_DIR: {OBJECTS_DIR}
KEA_TOOLS_ROOT: {KEA_TOOLS_ROOT}
EXISTING_FILES: {EXISTING_OBJECTS（incremental 时）}
```

等待完成，处理返回状态：

- **DONE** → 继续硬门检查
- **DONE_WITH_CONCERNS** → 展示疑虑清单，等待用户逐项处置（A 保留 / B 删除 / C 合并），完成后继续硬门检查
- **NEEDS_CONTEXT** → 展示缺失信息，补充后重新 Dispatch
- **BLOCKED** → 展示卡点，询问用户处置方式

**硬门检查（自动，不打断用户）**

```bash
cd {PROJECT_ROOT} && python3 -m kea --format json validate {OBJECTS_DIR}
```

- `errors = 0` 且 dead_links（category=`引用失效`）= 0 → **静默继续 Step 4b**
- 任一不满足 → 展示错误明细，等待用户指令（修复后重跑校验 → 通过后继续，或中止整个流水线）

**校验通过后**：运行 `kea parse` 更新 `OBJECT_REGISTRY`，供后续步骤使用：

```bash
python3 -m kea --format json parse {OBJECTS_DIR}
```

从输出中筛选 `type=object`，重建 `OBJECT_REGISTRY` 文本。

### Step 4b: 逻辑提取

**Dispatch extract-logic Subagent**

读取 `~/.claude/skills/kea/skills/extract-logic/SKILL.md`，Dispatch：

```
FLOWCHART_CANDIDATES: {Step 3 工具调用 1 生成的文本}
OBJECT_REGISTRY: {Step 4a 校验后更新的 OBJECT_REGISTRY}
SUMMARY_PATHS: {RESEARCH_REPORT_PATH},{INTERVIEW_SUMMARY_PATH}
LOGIC_DIR: {LOGIC_DIR}
KEA_TOOLS_ROOT: {KEA_TOOLS_ROOT}
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

1. 运行 `kea parse {LOGIC_DIR}` 更新 `LOGIC_REGISTRY`：

```bash
python3 -m kea --format json parse {LOGIC_DIR}
```

筛选 `type=logic`，重建 `LOGIC_REGISTRY` 文本。

2. 收集 `REFERENCED_ACTIONS`（供 Step 4c 使用）：扫描各逻辑文档"与动作(action)的关联"表的 `动作名称` 列和伪代码中 `call_action` 调用，去重，产出动作名称 + 引用计数列表。

### Step 4c: 动作提取

**Dispatch extract-actions Subagent**

读取 `~/.claude/skills/kea/skills/extract-actions/SKILL.md`，Dispatch：

```
REFERENCED_ACTIONS: {Step 4b 收集的动作候选列表文本}
LOGIC_REGISTRY: {Step 4b 校验后更新的 LOGIC_REGISTRY}
OBJECT_REGISTRY: {Step 4a 校验后更新的 OBJECT_REGISTRY}
ACTIONS_DIR: {ACTIONS_DIR}
KEA_TOOLS_ROOT: {KEA_TOOLS_ROOT}
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

**校验通过后**：运行 `kea parse {ACTIONS_DIR}` 更新 `ACTION_REGISTRY`：

```bash
python3 -m kea --format json parse {ACTIONS_DIR}
```

筛选 `type=action`，重建 `ACTION_REGISTRY` 文本。

### Step 4d: 规则提取

**规则候选预扫描**（LLM 读取已有文档）：

扫描 objects/logic/actions 目录下文档，识别潜在规则候选：
- 逻辑文档判断节点中的数值阈值条件（金额 > N、数量 > N）
- 逻辑/动作描述中包含"必须"/"不得"/"要求"的句子
- 动作文档中 required=是 的参数隐含的校验规则
- 动作文档异常处理中的违规场景

展示候选清单并询问用户：

```
发现潜在规则候选（共 {R} 条）：

  策略规则（跨对象）：
  • {规则名} — 来源：{文件}

  校验规则（字段约束）：
  • {规则名} — 来源：{文件}

  推导规则（计算公式）：
  • {规则名} — 来源：{文件}

请确认：
  ✅ 全部提取
  🗑️ 排除 {编号}：[原因]
  ➕ 补充：[描述额外规则]
  ❌ 该领域无独立规则 → 跳过提取，直接进入 Step 5 确认
```

**Dispatch extract-rules Subagent**（仅当有候选规则时）

读取 `~/.claude/skills/kea/skills/extract-rules/SKILL.md`，Dispatch：

```
RULE_CANDIDATES: {用户确认后的规则候选列表文本}
LOGIC_REGISTRY: {Step 4b 校验后更新的 LOGIC_REGISTRY}
ACTION_REGISTRY: {Step 4c 校验后更新的 ACTION_REGISTRY}
OBJECT_REGISTRY: {Step 4a 校验后更新的 OBJECT_REGISTRY}
RULES_DIR: {RULES_DIR}
KEA_TOOLS_ROOT: {KEA_TOOLS_ROOT}
SUMMARY_PATHS: {RESEARCH_REPORT_PATH}
EXISTING_FILES: {EXISTING_RULES（incremental 时）}
```

处理返回状态（同 Step 4a 模式）。

**硬门检查（自动，仅当 RULES_DIR 下有文件时）**

```bash
cd {PROJECT_ROOT} && python3 -m kea --format json validate {RULES_DIR}
```

- `errors = 0` 且 dead_links = 0 → **静默继续 Step 5**
- 任一不满足 → 展示错误明细，等待用户指令

### Step 5: 综合摘要与专家确认

展示全部提取结果摘要，引导专家在 Obsidian 中审视：

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
  ➕ 缺少 {名称}：[说明业务含义和所属类型]
```

- **确认** → 门控通过，进入 Step 6
- **需要修改** → 执行修改 → 重新运行对应类型的 `kea validate` → 询问是否继续
- **缺少** → 对应类型增量重提取（回到对应 Step 4x）→ 硬门 → 回到 Step 5

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

硬门失败时（任意 Step 4x 的 `kea validate` 返回 `errors > 0` 或 `dead_links > 0`）：

| 失败位置 | 优先处理方式 | 无法修复时回退目标 |
|---------|------------|-----------------|
| Step 4a 对象硬门 | 当前阶段内修复文件 | Phase 4（流程图） |
| Step 4b 逻辑硬门（dead_links） | 检查 `[[链接]]` 是否指向已有对象 → Step 4a 补充提取 | Phase 4 |
| Step 4c 动作硬门 | 当前阶段内修复文件 | Step 4b 补充逻辑 |
| Step 4d 规则硬门 | 当前阶段内修复文件 | Step 4a/4b/4c 补充对应文件 |
