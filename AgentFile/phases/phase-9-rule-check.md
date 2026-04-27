# Phase 9: 结构校验（Rule Check）

## 定位

本体萃取技能链第 9 阶段。对全部 Ontology 文档进行结构性规则检查，确保格式合规、引用完整、模板字段齐全。**本阶段错误 = 0 是硬性要求，不可人工覆盖。**

## 输入参数

| 参数 | 说明 |
|------|------|
| `DOMAIN_CN` / `DOMAIN_EN` | 领域名 |
| `VAULT_PATH` | Vault 路径 |
| `CHAIN_STATE_PATH` | chain-state 文件路径 |
| `OBJECTS_DIR` / `LOGIC_DIR` / `ACTIONS_DIR` / `RULES_DIR` | 各类型目录 |

## 前置条件检查

确认 Phase 8 状态为 `✅ 通过`，否则终止。

## 执行步骤

### Step 1: 更新 chain-state.md 为 in_progress

### Step 2: Dispatch 结构校验 Agent

读取 `~/.claude/skills/kea/skills/rule-check/SKILL.md`（参考实现中存在），Dispatch，全量模式：

```
OBJECTS_DIR: {OBJECTS_DIR}
LOGIC_DIR: {LOGIC_DIR}
ACTIONS_DIR: {ACTIONS_DIR}
RULES_DIR: {RULES_DIR}
MODE: full
```

等待完成，获取 JSON 格式问题报告。

**若 KEA 尚无 rule-check-agent.md**，改为运行 Python 工具层：

```bash
cd {PROJECT_ROOT} && python3 -m kea validate \
  --objects {OBJECTS_DIR} \
  --logic {LOGIC_DIR} \
  --actions {ACTIONS_DIR} \
  --rules {RULES_DIR} \
  --format json
```

### Step 3: 分类问题

将问题分为两类（参考 ontology-validate.md 的 A3 分类逻辑）：

**简单问题（可自动修复）**：
- 死链（`[[X]]` 无对应文件）
- 必填节缺失（`# 业务描述`、`# 输入` 等标题缺失）
- 表格列缺失

**复杂问题（需人类判断）**：
- 逻辑缺陷、参数未使用、子流程不匹配等所有语义类问题

### Step 4: 自动修复简单问题

对每个简单问题，提出修复方案并展示 diff，汇总展示：

```
已自动修复 {N} 个结构性问题：

| # | 文件 | 问题 | 修复内容 |
|---|------|------|---------|
| 1 | logic/xx.md | [[Y]] 无对应文件 | 移除失效链接 |
...

确认以上修改？[确认 / 逐条检查 / 全部撤销]
```

### Step 5: 复杂问题处理

展示复杂问题列表，询问处理哪些：

```
还有 {M} 个需要业务判断的问题：

1. ❌ [逻辑缺陷] logic/xx.md → {message}
2. ⚠️ [参数未使用] logic/yy.md → {message}

要处理哪些？[全部 / 输入编号如 1,3 / 跳过]
```

逐条处理，提供修改方案，允许用户提供自己的方案或跳过。

### Step 6: 回归校验

修复完成后，**重新 Dispatch rule-check-agent**，过滤掉已知问题，仅报告新出现的问题（回归检查）。

如有新问题，重复 Step 3-5-6，直到无新问题或用户选择跳过回归问题。

### Step 7: 保存报告

报告保存至：
```
{VAULT_PATH}/RAWData/KEAOutput/reports/validation/{YYYY-MM-DD}-{DOMAIN_EN}-rule-check.md
```

## 门控评估（G9）

### 自动验证项

| 条件 | 通过标准 | 是否可绕过 |
|------|---------|---------|
| ① 结构错误数 = 0 | 必须为 0 | **❌ 硬性，不可绕过** |
| ② 所有警告已处理 | 每条警告标注"已修复"或"已接受（写明原因）" | 可接受但需说明 |
| ③ 报告已保存 | 报告文件存在 | ❌ 不可绕过 |

**硬性规则**：如果 ① 不满足（仍有错误），无论人类是否说"确认"，本阶段**不通过**，必须修复。

### 人类确认

错误 = 0、所有警告已处理后，询问：

> "结构校验问题已处理完毕（错误 0，警告 {W} 条已处理）。
>
> - ✅ 确认：结构校验问题处理完毕
> - ✏️ 还需调整 [说明]"

## 门控通过 → 更新 chain-state.md

```markdown
| 9 | 结构校验 | ✅ 通过 | {YYYY-MM-DD HH:MM} | 错误0，警告{W}已处理 |
```

门控记录：

```markdown
### G9 通过记录（{YYYY-MM-DD HH:MM}）
- 结构错误：0 ✅（硬性）
- 警告：{W} 条，全部已处理 ✅
- 自动修复：{N} 条
- 人工处理：{M} 条
- 跳过（已接受）：{K} 条
- 报告路径：reports/validation/{filename} ✅
- 人类确认："结构校验问题处理完毕" ✅
```

更新 `current_phase: 10`。

## 门控失败 → 回退处理

**结构错误 > 0（修复后仍有错误）**：
- 这是当前阶段内的问题，不触发跨阶段回退
- 继续修复直到错误 = 0
- 如果错误指向的是 Phase 5/6/7/8 的输出质量问题（如大量字段缺失），则判断是否需要回退对应阶段

**回退触发条件**：若同一类型错误（如"主键缺失"）在超过 30% 的对象文档中出现，说明对应提取阶段质量不达标，**回退到 Phase 5/6/7/8 对应阶段**全量重修。

在 chain-state.md 追加回退记录（如发生跨阶段回退）。
