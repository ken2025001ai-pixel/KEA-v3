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
| `OBJECTS_DIR` | objects 目录 |
| `LOGIC_DIR` | logic 目录 |
| `ACTIONS_DIR` | actions 目录 |

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

### Step 4: Dispatch 规则提取 Agent（如有候选）

读取 `~/.claude/skills/kea/skills/extract-rules/SKILL.md`，Dispatch：

```
LOGIC_DIR: {LOGIC_DIR}
ACTIONS_DIR: {ACTIONS_DIR}
OBJECTS_DIR: {OBJECTS_DIR}
RULES_DIR: {VAULT_PATH}/30-Ontology/rules/{DOMAIN_EN}/
SUMMARY_PATHS: {RESEARCH_REPORT_PATH}
补充提取目标: {用户确认的候选规则名（如有范围限制）}
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

## 门控评估（G8）

### 自动验证项（当存在规则文档时）

| 条件 | 检查方式 | 通过标准 |
|------|---------|---------|
| ① constrains/guards 目标存在 | 提取每条规则 relations 中的目标，检查对应文件是否存在 | 不存在目标 = 0 |
| ② 规则条件字段有效 | 对于 validation/derivation 规则，检查条件中引用的字段名是否存在于目标对象属性表（中文名称列） | 无效字段 = 0 |
| ③ 结构错误 | 运行 rule-check-agent（仅 rules 范围） | 错误 = 0 |

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
