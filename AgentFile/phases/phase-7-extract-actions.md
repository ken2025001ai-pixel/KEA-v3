# Phase 7: 动作提取（Action Extraction）

## 定位

本体萃取技能链第 7 阶段。从逻辑文档的"与动作关联"表和逻辑描述中提取所有动作，确保每个动作都有完整的参数定义和异常处理，且无孤立动作。

## 输入参数

| 参数 | 说明 |
|------|------|
| `DOMAIN_CN` / `DOMAIN_EN` | 领域名 |
| `VAULT_PATH` | Vault 路径 |
| `CHAIN_STATE_PATH` | chain-state 文件路径 |
| `RESEARCH_REPORT_PATH` | G1 调研报告路径 |
| `INTERVIEW_SUMMARY_PATH` | G2 访谈摘要路径 |
| `OBJECTS_DIR` | `Phase 5 输出对象目录（Step 2.5 由工具扫描，结果以 OBJECT_REGISTRY 形式传入 subagent）` |
| `LOGIC_DIR` | `Phase 6 输出逻辑目录（Step 2.5 由工具扫描，结果以 LOGIC_REGISTRY 形式传入 subagent）` |
| `COVERAGE_THRESHOLD` | 覆盖率阈值 |

## 前置条件检查

确认 Phase 6 状态为 `✅ 通过`，否则终止。

## 执行步骤

### Step 1: 确定提取模式

检查 `{VAULT_PATH}/30-Ontology/actions/{DOMAIN_EN}/`：

- 为空 → `MODE = full`
- 有文件 → `MODE = incremental`

### Step 2: 更新 chain-state.md 为 in_progress

### Step 2.5: 预处理逻辑注册表与对象注册表

**工具调用 1**：扫描逻辑文档

```bash
python3 -m kea --format json parse {LOGIC_DIR}
```

**成功**（`count > 0`）→ 筛选 `type=logic`，生成 `LOGIC_REGISTRY` 文本：

```
已确认逻辑（{N} 个）：

{逻辑名} (id={id})
  关联动作：{动作名1}, {动作名2} ...（来自 relations type=calls）
  输入对象：{对象名1}, {对象名2} ...
  输出对象：{对象名1} ...

{逻辑名} (id={id})
  ...
```

**失败**（count = 0 或命令报错）→ 展示错误详情，询问用户：
- A 检查 LOGIC_DIR 路径后重试
- B 跳过工具扫描（LOGIC_REGISTRY 留空，subagent 将缺少逻辑注册表，part_of 关系声明需手工补充）

---

**工具调用 2**：扫描对象文档

```bash
python3 -m kea --format json parse {OBJECTS_DIR}
```

**成功**（`count > 0`）→ 生成 `OBJECT_REGISTRY` 文本：

```
已确认对象（{N} 个）：

{对象名} (id={id})
  属性：{属性名}[{类型},主键], {属性名}[{类型}] ...
```

**失败** → 展示错误详情，询问用户：
- A 检查 OBJECTS_DIR 路径后重试
- B 跳过扫描（OBJECT_REGISTRY 留空，subagent 将无法校验对象链接有效性）

### Step 3: 收集动作候选清单

在 Dispatch 前，先扫描所有逻辑文档，收集**已引用的动作名称**：

- 从每个逻辑文档的"与动作(action)的关联"表中提取 `动作名称` 列
- 从逻辑描述中提取 `调用[[动作名称]]` / `执行[[动作名称]]` 模式
- 去重，产出 `REFERENCED_ACTIONS` 列表

展示给用户：
```
逻辑文档中引用的动作（共 {M} 个）：
  • {动作1}（被 {N} 个逻辑引用）
  • {动作2}（被 {N} 个逻辑引用）
  ...
```

### Step 4: Dispatch 动作提取 Agent

读取 `~/.claude/skills/kea/skills/extract-actions/SKILL.md`，Dispatch：

```
REFERENCED_ACTIONS: {Step 3 已收集的动作候选列表文本}
LOGIC_REGISTRY: {Step 2.5 生成的逻辑注册表文本}
OBJECT_REGISTRY: {Step 2.5 生成的对象注册表文本}
ACTIONS_DIR: {VAULT_PATH}/30-Ontology/actions/{DOMAIN_EN}/
SUMMARY_PATHS: {RESEARCH_REPORT_PATH},{INTERVIEW_SUMMARY_PATH}
EXISTING_FILES: {EXISTING_FILES（如有）}
```

等待完成，读取返回状态。

### Step 4.5: 处理提取结果

根据 sub-skill 返回状态码处理：

**DONE** → 进入 Step 5

**DONE_WITH_CONCERNS** → 疑虑前置：展示疑虑清单（如"动作 X 参数信息不足，仅生成框架"），等待用户逐项处置。

**NEEDS_CONTEXT / BLOCKED** → 展示问题，询问用户处置。

### Step 4.6: 专家审视动作文件

> "已生成 {M} 个动作文件，请在 Obsidian 中审视：
>
> 📂 `30-Ontology/actions/{DOMAIN_EN}/`
>
> 每个文件包含：动作描述、触发条件、输入输出参数、异常处理。
> Graph View 中绿色节点 = 业务动作。
>
> 审视完毕后回复"继续"进入自动校验。"

等待用户回复后继续。

### Step 5: Dispatch 覆盖率检查 Agent

```
SOURCE_PATHS: {DIAGRAMS_DIR},{RESEARCH_REPORT_PATH},{INTERVIEW_SUMMARY_PATH}
LOGIC_DIR: {LOGIC_DIR}
ACTIONS_DIR: {VAULT_PATH}/30-Ontology/actions/{DOMAIN_EN}/
CHECK_TYPE: actions
```

等待完成。根据返回结果：
- **返回有效覆盖率报告** → 获取覆盖率数值，进入 Step 6
- **返回空或格式异常** → 询问用户是否跳过覆盖率检查
- **BLOCKED / NEEDS_CONTEXT** → 展示原因，询问用户处置
    
### Step 6: 运行 kea validate 结构校验

```bash
cd {PROJECT_ROOT} && python3 -m kea --format json validate {ACTIONS_DIR}
```

从 JSON 输出中提取：
- `errors` — 结构错误数（条件 ⑥）
- `reports[].issues[]` 中 category=`孤立动作` 的 issue（条件 ③）
- `reports[].issues[]` 中 category=`输入缺失` / `输出缺失` 的 issue（条件 ⑤）

条件 ④（每个动作有异常处理）需额外手工检查：Grep `# 异常处理` 节内容非空。

若 `errors > 0`，展示错误明细，询问用户处置方式。

## 门控评估（G7）

### 自动验证项

| 条件 | 检查方式 | 通过标准 |
|------|---------|---------|
| ① 引用动作全部有文件 | 对比 `REFERENCED_ACTIONS` 与 actions/{DOMAIN_EN}/ 目录文件名 | 未提取数 = 0 |
| ② 覆盖率 | 读取 coverage-check 报告 | ≥ COVERAGE_THRESHOLD% |
| ③ 孤立动作 = 0 | `kea validate` 输出中 category=`孤立动作` 的 issue | 孤立动作 = 0 |
| ④ 每个动作有异常处理 | Grep 每个动作文件中 `# 异常处理` 节内容非空 | 全部有异常处理节 |
| ⑤ 输入输出参数完整 | `kea validate` 输出中 category=`输入缺失`/`输出缺失` 的 issue | 缺失 = 0 |
| ⑥ 结构错误 | `kea validate` 输出的 `errors` 字段 | 错误 = 0 |

**条件 ①** 是关键：逻辑文档引用的动作必须 100% 有对应文件，否则逻辑文档中存在无法解析的引用。

### 人类确认

自动验证全部通过后，展示校验摘要，询问最终确认：

> "您已在 Obsidian 中审视过动作文件。请最终确认：
>
> - ✅ 确认：动作定义准确
> - ✏️ 需要修改 {动作名}：[说明修改内容]
> - ➕ 还有动作：{动作名} — [说明其业务含义和触发条件]"

## 门控通过 → 更新 chain-state.md

```markdown
| 7 | 动作提取 | ✅ 通过 | {YYYY-MM-DD HH:MM} | 提取{M}个，覆盖率{X}%，孤立动作0 |
```

更新 `current_phase: 8`。

## 门控失败 → 回退处理

| 失败条件 | 回退目标 | 处置方式 |
|---------|---------|---------|
| ① 引用动作未提取 | Phase 7（当前，增量） | 补充提取缺失动作 |
| ③ 孤立动作 > 0 | Phase 6 | 在逻辑文档中建立引用关系，或删除无意义孤立动作 |
| ② 覆盖率不足 | Phase 7（当前，增量） | 补充提取 |
| ④⑤ 内容不完整 | Phase 7（当前） | 修复对应动作文件 |
| ⑥ 结构错误 | Phase 7（当前） | 修复对应文件 |
