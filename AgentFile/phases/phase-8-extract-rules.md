# Phase 8: 规则提取（Rule Extraction）

## 定位

本体萃取技能链第 8 阶段。从对象、逻辑、动作文档和源材料中识别业务规则，提取为独立规则文档。本阶段可能输出零条规则（允许），但必须有人类专家明确确认"该领域无需独立规则文档"。

## 输入参数

| 参数 | 说明 |
|------|------|
| `DOMAIN_CN` / `DOMAIN_EN` | 领域名 |
| `VAULT_PATH` | Vault 路径 |
| `CHAIN_STATE_PATH` | chain-state 文件路径 |
| `RESEARCH_REPORT_PATH` | G1 调研报告路径 |
| `OBJECTS_DIR` | objects 目录（Step 2.5 由工具扫描，结果以 OBJECT_REGISTRY 形式传入 subagent） |
| `LOGIC_DIR` | logic 目录（Step 2.5 由工具扫描，结果以 LOGIC_REGISTRY 形式传入 subagent） |
| `ACTIONS_DIR` | actions 目录（Step 2.5 由工具扫描，结果以 ACTION_REGISTRY 形式传入 subagent） |

## 前置条件检查

确认 Phase 7 状态为 `✅ 通过`，否则终止。

## 执行步骤

### Step 1: 规则候选预扫描

在 Dispatch 前，快速扫描已有文档，识别潜在规则候选：

- 逻辑文档中的数值阈值条件（金额 > N、数量 > N）
- 逻辑文档的业务描述中包含"必须"/"不得"/"要求"的句子
- 动作文档的输入参数约束（required=是 的参数隐含的校验规则）
- 动作文档的异常处理中的违规场景

展示候选清单：

```
发现潜在规则候选（共 {R} 条）：

  策略规则（跨对象）：
  • {金额阈值规则} — 来源：logic/xx.md 判断节点
  
  校验规则（字段约束）：
  • {字段非空规则} — 来源：action/xx.md 输入参数
  
  推导规则（计算公式）：
  • {金额计算规则} — 来源：object/xx.md 属性描述
```

### Step 2: 询问用户确认候选范围

> "我发现了上述 {R} 条潜在规则候选。
>
> - ✅ 全部提取
> - 🗑️ 排除 {编号}：[原因]
> - ➕ 补充：[描述额外规则]
> - ❌ 该领域无独立规则 → 直接进入 G6 确认"

### Step 3: 更新 chain-state.md 为 in_progress

### Step 2.5: 预处理逻辑/动作/对象注册表

**工具调用 1**：扫描逻辑文档

```bash
python3 -m kea --format json parse {LOGIC_DIR}
```

**成功**（`count > 0`）→ 筛选 `type=logic`，生成 `LOGIC_REGISTRY` 文本：

```
已确认逻辑（{N} 个）：

{逻辑名} (id={id})
  前置条件：{前置条件描述} ...
  关联动作：{动作名1}, {动作名2} ...
```

**失败** → 展示错误详情，询问用户：
- A 检查 LOGIC_DIR 路径后重试
- B 跳过扫描（LOGIC_REGISTRY 留空，subagent 将缺少逻辑注册表，guards 关系声明需手工补充）

---

**工具调用 2**：扫描动作文档

```bash
python3 -m kea --format json parse {ACTIONS_DIR}
```

**成功**（`count > 0`）→ 筛选 `type=action`，生成 `ACTION_REGISTRY` 文本：

```
已确认动作（{N} 个）：

{动作名} (id={id})
  所属逻辑：{逻辑名} (id={id})
  输入约束：{参数名}[{类型},required={true|false}] ...
  操作对象：{对象名}[uses|modifies] ...
```

**失败** → 展示错误详情，询问用户：
- A 检查 ACTIONS_DIR 路径后重试
- B 跳过扫描（ACTION_REGISTRY 留空，subagent 将缺少动作注册表，constrains 关系声明需手工补充）

---

**工具调用 3**：扫描对象文档

```bash
python3 -m kea --format json parse {OBJECTS_DIR}
```

**成功**（`count > 0`）→ 生成 `OBJECT_REGISTRY` 文本：

```
已确认对象（{N} 个）：

{对象名} (id={id})
  属性：{属性名}[{类型},主键], {属性名}[{类型}] ...
```

**失败** → 询问 A 重试 / B 跳过（OBJECT_REGISTRY 留空，subagent 将无法校验对象字段引用有效性）

### Step 4: Dispatch 规则提取 Agent（如有候选）

读取 `~/.claude/skills/kea/skills/extract-rules/SKILL.md`，Dispatch：

```
RULE_CANDIDATES: {Step 1/2 收集并经用户确认的规则候选列表文本}
LOGIC_REGISTRY: {Step 2.5 生成的逻辑注册表文本}
ACTION_REGISTRY: {Step 2.5 生成的动作注册表文本}
OBJECT_REGISTRY: {Step 2.5 生成的对象注册表文本}
RULES_DIR: {VAULT_PATH}/30-Ontology/rules/{DOMAIN_EN}/
SUMMARY_PATHS: {RESEARCH_REPORT_PATH}
补充提取目标: {用户确认的候选规则名（如有范围限制）}
EXISTING_FILES: {EXISTING_FILES（如有）}
```

等待完成，读取返回状态。

根据 sub-skill 返回状态码处理（同 Phase 5-7 模式：DONE / DONE_WITH_CONCERNS / NEEDS_CONTEXT / BLOCKED）。

如有规则文档生成，引导专家在 Obsidian 中审视：

> "已生成 {R} 条规则文件，请在 Obsidian 中审视：
>
> 📂 `30-Ontology/rules/{DOMAIN_EN}/`
>
> 每个文件包含：规则描述、适用范围、规则条件(IF/THEN)、违规处理。
> Graph View 中橙色节点 = 业务规则。
>
> 审视完毕后回复"继续"进入自动校验。"

### Step N: 运行 kea validate 结构校验（如有规则文档）

若 `RULES_DIR` 下有 `.md` 文件：

```bash
cd {PROJECT_ROOT} && python3 -m kea --format json validate {RULES_DIR}
```

从 JSON 输出中提取：
- `errors` — 结构错误数（条件 ③）
- `reports[].issues[]` 中 category=`引用失效` 的 issue — 目标对象不存在（条件 ①）
- `reports[].issues[]` 中 category=`字段不存在` 的 issue（条件 ②）

若 `errors > 0`，展示错误明细，询问用户处置方式。

**无规则文档时**：跳过本步骤。

## 门控评估（G8）

### 自动验证项（当存在规则文档时）

| 条件 | 检查方式 | 通过标准 |
|------|---------|---------|
| ① constrains/guards 目标存在 | `kea validate` 输出中 category=`引用失效` 的 issue | 不存在目标 = 0 |
| ② 规则条件字段有效 | `kea validate` 输出中 category=`字段不存在` 的 issue | 无效字段 = 0 |
| ③ 结构错误 | `kea validate` 输出的 `errors` 字段 | 错误 = 0 |

**无规则文档时**：条件 ①②③ 自动通过（N/A），仅需人类确认。

### 人类确认

**有规则文档时**询问：

> "以上 {R} 条规则定义是否准确？
>
> - ✅ 确认：规则准确
> - ✏️ 需要修改 {规则名}：[说明修改内容]"

**无规则文档时**询问：

> "本阶段未提取任何独立规则文档。请确认：
>
> - ✅ 确认：该领域无需独立规则文档，相关约束已内嵌于对象/逻辑/动作文档中
> - ➕ 补充规则：[说明规则内容]"

## 门控通过 → 更新 chain-state.md

```markdown
| 8 | 规则提取 | ✅ 通过 | {YYYY-MM-DD HH:MM} | 提取{R}条（或"无独立规则"） |
```

门控记录中记录规则数、类型分布（或"无独立规则，已确认"）。

更新 `current_phase: 9`。

## 门控失败 → 回退处理

| 失败条件 | 回退目标 | 处置方式 |
|---------|---------|---------|
| ① 目标文件不存在 | 对应的 Phase 5/6/7 | 补充提取缺失的对象/逻辑/动作文件 |
| ② 字段不存在 | Phase 5（对象） | 在对象属性表中补充缺失字段 |
| ③ 结构错误 | Phase 8（当前） | 修复规则文件 |
